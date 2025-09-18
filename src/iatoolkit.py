# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit Core
# Framework opensource para chatbots empresariales con IA

from flask import Flask, url_for
from flask_session import Session
from flask_injector import FlaskInjector
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from urllib.parse import urlparse
import redis
import logging
import os
import click
from functools import partial
from typing import Optional
from injector import Injector, Binder, singleton

from .repositories.database_manager import DatabaseManager
from src.services.company_registry import CompanyRegistry
from src.services.dispatcher_service import Dispatcher
from common.routes import register_routes

VERSION = "2.0.0"


class IAToolkit:
    """
    Clase principal del framework IAToolkit
    Crea y configura aplicaciones Flask con soporte para empresas dinámicas
    """

    def __init__(self,
                 companies_config: Optional[str] = None,
                 iatoolkit_config: Optional[str] = None):
        """
        Inicializa el toolkit

        Args:
            companies_config: Ruta al archivo YAML de configuración de empresas
            iatoolkit_config: Ruta al archivo YAML de configuración del core (opcional)
        """
        self.companies_config = companies_config
        self.iatoolkit_config = iatoolkit_config
        self.app = None
        self.db_manager = None
        self.company_registry = None
        self.dispatcher = None
        self._injector = None

    def create_app(self) -> Flask:
        """
        Crea y configura la aplicación Flask
        """
        # 1. Configurar logging base
        self._setup_logging()

        # 2. Crear instancia Flask
        self.app = Flask(__name__,
                         static_folder=self._get_static_folder(),
                         template_folder=self._get_template_folder())

        # 3. Configurar Flask básico
        self._configure_flask_basic()

        # 4. Configurar base de datos
        self._setup_database()

        # 5. Configurar Redis y sesiones
        self._setup_redis_sessions()

        # 6. Configurar CORS
        self._setup_cors()

        # 7. Configurar registry de empresas
        self._setup_company_registry()

        # 8. Configurar inyección de dependencias
        self._setup_dependency_injection()

        # 9. Registrar rutas
        self._register_routes()

        # 10. Configurar otros servicios
        self._setup_additional_services()

        # 11. Configurar CLI commands
        self._setup_cli_commands()

        # 12. Context processors
        self._setup_context_processors()

        logging.info(f"IAToolkit v{VERSION} inicializado correctamente")
        return self.app

    def _setup_logging(self):
        """Configura el sistema de logging"""
        log_level = logging.INFO if os.getenv("FLASK_ENV") == 'development' else logging.WARNING

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - IATOOLKIT - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )

        # Configurar niveles de librerías externas
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)

    def _configure_flask_basic(self):
        """Configuraciones básicas de Flask"""
        self.app.config['VERSION'] = VERSION
        self.app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'iatoolkit-default-secret')

        # Configuración de cookies y sesiones
        is_https = os.getenv("USE_HTTPS", "false").lower() == "true"
        self.app.config["SESSION_COOKIE_SAMESITE"] = "None" if is_https else "Lax"
        self.app.config["SESSION_COOKIE_SECURE"] = is_https
        self.app.config['SESSION_PERMANENT'] = False
        self.app.config['SESSION_USE_SIGNER'] = True

        # Configuración JWT
        self.app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'iatoolkit-jwt-secret')
        self.app.config['JWT_ALGORITHM'] = 'HS256'
        self.app.config['JWT_EXPIRATION_SECONDS_CHAT'] = int(os.getenv('JWT_EXPIRATION_SECONDS_CHAT', 3600))

        # Configuración para tokenizers (si se usa)
        if os.getenv('FLASK_ENV') == 'development':
            os.environ["TOKENIZERS_PARALLELISM"] = "false"

    def _setup_database(self):
        """Configura el gestor de base de datos"""
        database_uri = os.getenv('DATABASE_URI')
        if not database_uri:
            raise IAToolkitException("DATABASE_URI es requerida")

        self.db_manager = DatabaseManager(database_uri)
        self.db_manager.create_all()
        logging.info("Base de datos configurada correctamente")

    def _setup_redis_sessions(self):
        """Configura Redis y las sesiones"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logging.warning("REDIS_URL no configurada, usando sesiones en memoria")
            return

        try:
            url = urlparse(redis_url)
            redis_instance = redis.Redis(
                host=url.hostname,
                port=url.port,
                password=url.password,
                ssl=(url.scheme == "rediss"),
                ssl_cert_reqs=None
            )

            self.app.config['SESSION_TYPE'] = 'redis'
            self.app.config['SESSION_REDIS'] = redis_instance

            Session(self.app)
            logging.info("Redis y sesiones configurados correctamente")

        except Exception as e:
            logging.error(f"Error configurando Redis: {e}")
            # Continuar sin Redis

    def _setup_cors(self):
        """Configura CORS"""
        # Origins por defecto para desarrollo
        default_origins = [
            "http://localhost:3000",
            "http://localhost:5001",
            "http://127.0.0.1:5001"
        ]

        # Obtener origins adicionales desde variables de entorno
        extra_origins = []
        for i in range(1, 6):  # Soporte para CORS_ORIGIN_1 a CORS_ORIGIN_5
            origin = os.getenv(f'CORS_ORIGIN_{i}')
            if origin:
                extra_origins.append(origin)

        all_origins = default_origins + extra_origins

        CORS(self.app,
             supports_credentials=True,
             origins=all_origins,
             allow_headers=[
                 "Content-Type", "Authorization", "X-Requested-With",
                 "X-Chat-Token", "x-chat-token"
             ],
             methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

        logging.info(f"CORS configurado para: {all_origins}")

    def _setup_company_registry(self):
        """Configura el registry de empresas"""
        if not self.companies_config or not os.path.exists(self.companies_config):
            logging.warning("No se encontró configuración de empresas, sistema sin empresas")
            self.company_registry = CompanyRegistry(None)
            return

        self.company_registry = CompanyRegistry(self.companies_config)
        self.company_registry.discover_and_register_companies()

        registered = list(self.company_registry.get_enabled_companies().keys())
        logging.info(f"Empresas registradas: {registered}")

    def _setup_dependency_injection(self):
        """Configura el sistema de inyección de dependencias"""
        FlaskInjector(
            app=self.app,
            modules=[partial(self._configure_dependencies)]
        )

    def _configure_dependencies(self, binder: Binder):
        """Configura todas las dependencias del sistema"""
        try:
            # Core dependencies
            binder.bind(DatabaseManager, to=self.db_manager, scope=singleton)
            binder.bind(CompanyRegistry, to=self.company_registry, scope=singleton)

            # Import core services
            from .repositories import (
                DocumentRepo, DocumentTypeRepo, ProfileRepo,
                LLMQueryRepo, VSRepo, TaskRepo
            )
            from .services import (
                QueryService, TaskService, BenchmarkService,
                DocumentService, PromptService, ExcelService,
                MailService, LoadDocumentsService, ProfileService,
                JWTService
            )
            from .infra import LLMProxy, GoogleChatApp, LLMClient, MailApp
            from common.auth import IAuthentication
            from common.util import Utility
            from .views import LLMQueryView

            # Bind repositories
            binder.bind(DocumentRepo, to=DocumentRepo)
            binder.bind(DocumentTypeRepo, to=DocumentTypeRepo)
            binder.bind(ProfileRepo, to=ProfileRepo)
            binder.bind(LLMQueryRepo, to=LLMQueryRepo)
            binder.bind(VSRepo, to=VSRepo)
            binder.bind(TaskRepo, to=TaskRepo)

            # Bind services
            binder.bind(QueryService, to=QueryService)
            binder.bind(TaskService, to=TaskService)
            binder.bind(BenchmarkService, to=BenchmarkService)
            binder.bind(DocumentService, to=DocumentService)
            binder.bind(PromptService, to=PromptService)
            binder.bind(ExcelService, to=ExcelService)
            binder.bind(MailService, to=MailService)
            binder.bind(LoadDocumentsService, to=LoadDocumentsService)
            binder.bind(ProfileService, to=ProfileService)
            binder.bind(JWTService, to=JWTService)

            # Bind infrastructure
            binder.bind(LLMProxy, to=LLMProxy, scope=singleton)
            binder.bind(LLMClient, to=LLMClient, scope=singleton)
            binder.bind(GoogleChatApp, to=GoogleChatApp)
            binder.bind(MailApp, to=MailApp)
            binder.bind(IAuthentication, to=IAuthentication)
            binder.bind(Utility, to=Utility)
            binder.bind(LLMQueryView, to=LLLQueryView)

            # Bind dispatcher DESPUÉS de configurar empresas
            binder.bind(Dispatcher, to=Dispatcher)

            # Configurar dependencias específicas de empresas registradas
            self._configure_company_dependencies(binder)

            logging.info("Dependencias configuradas correctamente")

        except Exception as e:
            logging.error(f"Error configurando dependencias: {e}")
            raise

    def _configure_company_dependencies(self, binder: Binder):
        """Configura dependencias específicas de cada empresa"""
        if not self.company_registry:
            return

        enabled_companies = self.company_registry.get_enabled_companies()

        for company_name, company_info in enabled_companies.items():
            try:
                company_class = company_info['class']

                # Si la empresa define configuración de dependencias, la ejecutamos
                if hasattr(company_class, 'configure_dependencies'):
                    logging.info(f"Configurando dependencias para {company_name}")
                    company_class.configure_dependencies(binder)

            except Exception as e:
                logging.error(f"Error configurando dependencias para {company_name}: {e}")

    def _register_routes(self):
        """Registra todas las rutas del sistema"""
        register_routes(self.app)

    def _setup_additional_services(self):
        """Configura servicios adicionales"""
        # Bcrypt para hashing de passwords
        Bcrypt(self.app)

    def _setup_cli_commands(self):
        """Configura comandos CLI del core"""

        @self.app.cli.command("init-db")
        def init_db():
            """Inicializa la base de datos del sistema"""
            try:
                injector = self._get_injector()
                dispatcher = injector.get(Dispatcher)

                click.echo("🚀 Inicializando base de datos...")
                dispatcher.init_db()
                click.echo("✅ Base de datos inicializada correctamente")

            except Exception as e:
                logging.exception(e)
                click.echo(f"❌ Error: {e}")

        @self.app.cli.command("start-companies")
        def start_companies():
            """Inicia la ejecución de todas las empresas"""
            try:
                injector = self._get_injector()
                dispatcher = injector.get(Dispatcher)

                click.echo("🏢 Iniciando empresas...")
                dispatcher.start_execution()
                click.echo("✅ Empresas iniciadas correctamente")

            except Exception as e:
                logging.exception(e)
                click.echo(f"❌ Error: {e}")

        @self.app.cli.command("list-companies")
        def list_companies():
            """Lista todas las empresas registradas"""
            if not self.company_registry:
                click.echo("No hay empresas registradas")
                return

            companies = self.company_registry.get_registered_companies()
            click.echo("📋 Empresas registradas:")

            for name, info in companies.items():
                status = "✅ Activa" if info['enabled'] else "❌ Inactiva"
                source = info.get('source', 'unknown')
                click.echo(f"  • {name}: {info['class'].__name__} ({status}) [{source}]")

    def _setup_context_processors(self):
        """Configura context processors para templates"""

        @self.app.context_processor
        def inject_globals():
            return {
                'url_for': url_for,
                'iatoolkit_version': VERSION,
                'app_name': 'IAToolkit'
            }

    def _get_injector(self) -> Injector:
        """Obtiene el injector actual"""
        if not self._injector:
            from flask_injector import get_injector
            self._injector = get_injector(self.app)
        return self._injector

    def _get_static_folder(self) -> str:
        """Obtiene la ruta de la carpeta static"""
        # Por defecto buscar en el paquete iatoolkit
        import iatoolkit
        base_path = os.path.dirname(iatoolkit.__file__)
        return os.path.join(base_path, 'static')

    def _get_template_folder(self) -> str:
        """Obtiene la ruta de la carpeta de templates"""
        import iatoolkit
        base_path = os.path.dirname(iatoolkit.__file__)
        return os.path.join(base_path, 'templates')

    # Métodos públicos para acceso externo
    def get_dispatcher(self) -> Dispatcher:
        """Obtiene el dispatcher del sistema"""
        if not self._injector:
            raise IAToolkitException("App no inicializada")
        return self._injector.get(Dispatcher)

    def get_database_manager(self) -> DatabaseManager:
        """Obtiene el database manager"""
        return self.db_manager

    def get_company_registry(self) -> CompanyRegistry:
        """Obtiene el registry de empresas"""
        return self.company_registry


# Función de conveniencia para inicialización rápida
def create_app(companies_config: Optional[str] = None,
               iatoolkit_config: Optional[str] = None) -> Flask:
    """
    Función de conveniencia para crear una app IAToolkit
    """
    toolkit = IAToolkit(companies_config, iatoolkit_config)
    return toolkit.create_app()


# Auto-startup para desarrollo
def _auto_startup():
    """Inicia empresas automáticamente si no estamos en testing"""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            from flask import current_app
            with current_app.app_context():
                from flask_injector import get_injector
                injector = get_injector(current_app)
                dispatcher = injector.get(Dispatcher)
                dispatcher.start_execution()
        except Exception as e:
            logging.exception(e)


# Registrar startup automático
from flask import Flask

Flask.before_first_request(_auto_startup)