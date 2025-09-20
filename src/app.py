# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import Flask, url_for
from flask_session import Session
from flask_injector import FlaskInjector
from flask_bcrypt import Bcrypt
from repositories.database_manager import DatabaseManager
from repositories.document_repo import DocumentRepo
from repositories.document_type_repo import DocumentTypeRepo
from repositories.profile_repo import ProfileRepo
from repositories.llm_query_repo import LLMQueryRepo
from repositories.vs_repo import VSRepo
from repositories.tasks_repo import TaskRepo
from services.query_service import QueryService
from services import Dispatcher
from services import LoadDocumentsService
from companies import MaxxaCluster
from services import TaskService
from services import ProfileService
from services import DocumentService
from services.prompt_manager_service import PromptService
from services.jwt_service import JWTService
from services.benchmark_service import BenchmarkService
from views.llmquery_view import LLMQueryView
from infra.llm_proxy import LLMProxy
from infra.google_chat_app import GoogleChatApp
from common.auth import IAuthentication
from infra.llm_client import llmClient
from infra.mail_app import MailApp
from common.util import Utility
from dotenv import load_dotenv
from common.routes import register_routes
from flask_cors import CORS
import logging
import redis
from urllib.parse import urlparse
from injector import Injector, Binder, singleton
import click
from functools import partial
from typing import Iterable
import os

VERSION = "1.5"


def create_app():
    # Configurar el nivel de logging
    log_level = logging.INFO if os.environ.get("FLASK_ENV", "development") == 'dev' else logging.WARNING
    logging.basicConfig(
        level=log_level,  # Nivel de registro: DEBUG, INFO, WARNING, ERROR, CRITICAL
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Formato del log
        handlers=[
            # logging.FileHandler("app.log"),  # Guardar en un archivo
            logging.StreamHandler()  # Mostrar en la consola
        ]
    )

    # init the Flask instance
    app = Flask(__name__, static_folder='static')
    app.config['VERSION'] = VERSION

    # create the database manager
    db_manager = DatabaseManager(os.getenv('DATABASE_URI'))
    db_manager.create_all()

    # detect if running under  HTTPS
    is_https = os.getenv("USE_HTTPS", "false").lower() == "true"

    # enable redis for the sessions
    url = urlparse(os.environ.get("REDIS_URL"))
    redis_instance = redis.Redis(host=url.hostname, port=url.port, password=url.password,
                                 ssl=(url.scheme == "rediss"), ssl_cert_reqs=None)
    app.config['SESSION_TYPE'] = 'redis'  # Usa Redis como backend para sesiones
    app.config['SESSION_REDIS'] = redis_instance  # Conexión a Redis
    app.config['SECRET_KEY'] = 'IAToolkit'  # Importante para proteger la sesión
    app.config['SESSION_PERMANENT'] = False  # Las sesiones no son permanentes
    app.config['SESSION_USE_SIGNER'] = True  # Firma las cookies de sesión para mayor seguridad

    # JWT for externals backend access
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'desarrollo-jwt-secret-muy-seguro')
    app.config['JWT_ALGORITHM'] = 'HS256'
    app.config['JWT_EXPIRATION_SECONDS_CHAT'] = int(os.getenv('JWT_EXPIRATION_SECONDS_CHAT', 3600))

    # enable cors
    app.config["SESSION_COOKIE_SAMESITE"] = "None" if is_https else "Lax"
    app.config["SESSION_COOKIE_SECURE"] = is_https
    CORS(app,
         supports_credentials=True,
         origins=[
             "http://localhost:5001",
             "http://127.0.0.1:5001",
             "https://portal-interno.maxxa.cl"
            ],
         allow_headers=[
             "Content-Type",
             "Authorization",
             "X-Requested-With",
             "X-Chat-Token",
             "x-chat-token",
         ],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         )

    # init Flask-Session
    Session(app)

    # register the routes
    register_routes(app)

    # init Flask-Injector
    FlaskInjector(app=app, modules=[partial(configure_dependencies, db_manager=db_manager)])

    # init Bcrypt for use with Flask
    bcrypt = Bcrypt(app)

    if os.getenv('FLASK_ENV') == 'dev':
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

    @app.context_processor
    def inject_url_for():
        return {'url_for': url_for}

    if not os.getenv("PYTEST_CURRENT_TEST"):
        # start company executions
        start_companies(db_manager)

        @app.cli.command("init-db")
        def init_db():
            """Comando CLI para inicializar la base de datos a través del Dispatcher."""
            injector = Injector([partial(configure_dependencies, db_manager=db_manager)])
            dispatcher = injector.get(Dispatcher)

            try:
                click.echo("Inicializando la base de datos...")
                dispatcher.init_db()
                click.echo("Base de datos inicializada correctamente.")
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error al inicializar la base de datos: {e}")

        @app.cli.command("load")
        def load_documents():
            injector = Injector([partial(configure_dependencies, db_manager=db_manager)])
            load_documents_service = injector.get(LoadDocumentsService)

            try:
                result = load_documents_service.load()
                click.echo(result['message'])
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

        @app.cli.command("cluster")
        @click.argument("n_clusters")
        def create_clusters(n_clusters):
            injector = Injector([partial(configure_dependencies, db_manager=db_manager)])
            maxxa_cluster = injector.get(MaxxaCluster)

            try:
                result = maxxa_cluster.create_customer_cluster(int(n_clusters))
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

        @app.cli.command("exec-tasks")
        @click.argument("company_short_name")
        def exec_pending_tasks(company_short_name: str):
            injector = Injector([lambda binder: configure_dependencies(binder, db_manager=db_manager)])
            task_service = injector.get(TaskService)

            try:
                result = task_service.trigger_pending_tasks(company_short_name)
                click.echo(result['message'])
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

        @app.cli.command("benchmark")
        @click.argument("company_short_name")
        @click.argument("file")
        def exec_benchmark(company_short_name: str, file: str):
            injector = Injector([lambda binder: configure_dependencies(binder, db_manager=db_manager)])
            benchmark_service = injector.get(BenchmarkService)

            try:
                output_file = benchmark_service.run(company_short_name, file)
                click.echo(click.style(f"\nBenchmark completado exitosamente.", fg='green'))
                click.echo(f"Los resultados han sido guardados en: {output_file}")
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

        @app.cli.command("api-key")
        @click.argument("company_short_name")
        def api_key(company_short_name: str):
            injector = Injector([lambda binder: configure_dependencies(binder, db_manager=db_manager)])
            profile_service = injector.get(ProfileService)

            try:
                result = profile_service.new_api_key(company_short_name)
                click.echo(result['message'])
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

        @app.cli.command("encrypt-key")
        @click.argument("key")
        def api_key(key: str):
            injector = Injector([lambda binder: configure_dependencies(binder, db_manager=db_manager)])
            util = injector.get(Utility)

            try:
                encrypt_key = util.encrypt_key(key)
                click.echo(f'la clave encriptada es: {encrypt_key} \n')
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

    return app

def configure_dependencies(binder: Binder, db_manager: DatabaseManager):
    try:
        binder.bind(DatabaseManager, to=db_manager, scope=singleton)
        binder.bind(LLMProxy, to=LLMProxy, scope=singleton)
        binder.bind(llmClient, to=llmClient, scope=singleton)
        binder.bind(Dispatcher,to=Dispatcher)

        binder.bind(DocumentRepo, to=DocumentRepo)
        binder.bind(DocumentTypeRepo, to=DocumentTypeRepo)
        binder.bind(ProfileRepo, to=ProfileRepo)
        binder.bind(TaskRepo, to=TaskRepo)
        binder.bind(LLMQueryRepo, to=LLMQueryRepo)
        binder.bind(VSRepo, to=VSRepo)

        binder.bind(ProfileService, to=ProfileService)
        binder.bind(QueryService, to=QueryService)
        binder.bind(TaskService, to=TaskService)
        binder.bind(BenchmarkService, to=BenchmarkService)
        binder.bind(DocumentService, to=DocumentService)
        binder.bind(GoogleChatApp, to=GoogleChatApp)
        binder.bind(LLMQueryView, to=LLMQueryView)
        binder.bind(PromptService, to=PromptService)
        binder.bind(IAuthentication, to=IAuthentication)
        binder.bind(MailApp, to=MailApp)
        binder.bind(JWTService, to=JWTService)

        binder.bind(MaxxaCluster, to=MaxxaCluster)
        binder.bind(Iterable[str], to=lambda: [])
    except TypeError as e:
        print(f"Error al configurar el Binder: {e}")


# start execution of every company
def start_companies(db_manager: DatabaseManager):
    injector = Injector([partial(configure_dependencies, db_manager=db_manager)])
    dispatcher = injector.get(Dispatcher)

    try:
        dispatcher.start_execution()
    except Exception as e:
        logging.exception(e)

# init the app
app = create_app()

if __name__ == "__main__":
    # only for local development
    load_dotenv()
    app.run(debug=True)
