# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit import BaseCompany
from iatoolkit import LoadDocumentsService, SearchService, SqlService
from injector import inject
from companies.sample_company.sample_database import SampleCompanyDatabase
import click
import logging


class SampleCompany(BaseCompany):
    @inject
    def __init__(self,
                sql_service: SqlService,
                search_service: SearchService,
                load_document_service: LoadDocumentsService,):
        super().__init__()
        self.sql_service = sql_service
        self.search_service = search_service
        self.load_document_service = load_document_service

    def handle_request(self, action: str, **kwargs) -> str:
        if action == "document_search":
            query_string = kwargs.get('query')
            return self.search_service.search(self.company_short_name, query_string)
        else:
            return self.unsupported_operation(action)


    def get_user_info(self, user_identifier: str) -> dict:
        user_data = {
            "id": user_identifier,
            "user_email": 'sample@sample_company.com',
            "user_fullname": 'Sample User',
            "extras": {}
        }
        return user_data


    def register_cli_commands(self, app):
        @app.cli.command("populate-database")
        def populate_sample_db():
            # get the handler to the database
            sample_db_manager = self.sql_service.get_database_manager('sample_database')
            self.sample_database = SampleCompanyDatabase(sample_db_manager)

            """📦 Crea y puebla la base de datos de sample_company."""
            if not self.sample_database:
                click.echo("❌ Error: La base de datos no está configurada.")
                click.echo("👉 Asegúrate de que 'SAMPLE_DATABASE_URI' esté definida en tu entorno.")
                return

            try:
                click.echo(
                    "⚙️  Creando y poblando la base de datos, esto puede tardar unos momentos...")
                self.sample_database.create_database()
                self.sample_database.populate_from_excel('companies/sample_company/sample_data/northwind.xlsx')
                click.echo("✅ Base de datos de poblada exitosamente.")
            except Exception as e:
                logging.exception(e)
                click.echo(f"❌ Ocurrió un error inesperado: {e}")

        @app.cli.command("load")
        def load_documents():
            try:
                self.load_document_service.load_sources(
                            company=self.company,
                            sources_to_load=["employee_contracts", "supplier_manuals"]
                        )
            except Exception as e:
                logging.exception(e)
                click.echo(f"Error: {str(e)}")

