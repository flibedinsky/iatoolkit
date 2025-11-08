# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit import IAToolkit, BaseCompany, DatabaseManager
from iatoolkit import SqlService, LoadDocumentsService, SearchService, ConfigurationService
from injector import inject
from companies.sample_company.sample_database import SampleCompanyDatabase
import os
import click
import logging


class SampleCompany(BaseCompany):
    @inject
    def __init__(self,
            config_service: ConfigurationService,
            sql_service: SqlService,
            search_service: SearchService):
        super().__init__()
        self.config_service = config_service
        self.sql_service = sql_service
        self.search_service = search_service
        self.sample_db_manager = None
        self.sample_database = None

        # get the company configuration
        config = self.config_service.get_company_content('sample_company', 'data_sources')
        db_env_var = config.get('sql', [{}])[0].get('connection_string_env')

        # connect to Internal database
        sample_db_uri = os.getenv(db_env_var) if db_env_var else None
        if not sample_db_uri:
            # if not exists use the same iatoolkit database
            sample_db_uri = os.getenv('DATABASE_URI')

        if sample_db_uri:
            self.sample_db_manager = DatabaseManager(sample_db_uri, register_pgvector=False)
            self.sample_database = SampleCompanyDatabase(self.sample_db_manager)

    def handle_request(self, action: str, **kwargs) -> str:
        if action == "sql_query":
            sql_query = kwargs.get('query')
            return self.sql_service.exec_sql(self.sample_db_manager, sql_query)
        elif action == "document_search":
            query_string = kwargs.get('query')
            return self.search_service.search(self.company.id, query_string)
        else:
            return self.unsupported_operation(action)

    # Return company specific context
    def get_company_context(self, **kwargs) -> str:
        if not self.sample_db_manager:
            return ''

        # get the configuration for 'data_sources' from the ConfigurationService
        data_sources_config = self.config_service.get_company_content(self.company_short_name, 'data_sources')
        if not data_sources_config or not data_sources_config.get('sql'):
            logging.warning(f"No 'data_sources.sql' configuration found for company '{self.company_short_name}'.")
            return ''

        # the first SQL source defined in the YAML configuration
        sql_source = data_sources_config['sql'][0]
        database_tables = sql_source.get('tables', [])
        db_description = sql_source.get('description', '')

        db_context = f"{db_description}\n" if db_description else ""
        for table_info in database_tables:
            try:
                table_name = table_info['table_name']

                # if schema_name is not defined, use table_name as default value.
                schema_name = table_info.get('schema_name', table_name)
                table_definition = self.sample_db_manager.get_table_schema(
                    table_name=table_name,
                    schema_name=schema_name,
                    exclude_columns=[]
                )
                db_context += table_definition
            except Exception as e:
                logging.warning(f"Advertencia al generar esquema para {table_info['table_name']}: {e}")

        return db_context

    def get_metadata_from_filename(self, filename: str) -> dict:
        if filename.startswith('contract_'):
            return {'type': 'employee_contract'}
        return {}

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
            if os.getenv('FLASK_ENV') == 'dev':
                connector_config = {'type': 'local', 'path': "" }

            else:
                connector_config = {'type': 's3',
                                  'bucket': "iatoolkit",
                                  'prefix': 'sample_company'}

            load_documents_service = IAToolkit.get_instance().get_injector().get(LoadDocumentsService)

            # documents are loaded from 2 different folders
            # as a sample, only add metadata 'type' for one of them: supplier_manual
            # for the other one, we will add metadata from the filename in get_metadata_from_filename method
            # metadata es optional always
            types_to_load = [
                {'type': 'supplier_manual', 'folder': 'supplier_manuals'},
                {'folder': 'employee_contracts'}
                ]

            for doc in types_to_load:
                connector_config['path'] = f"companies/sample_company/sample_data/{doc['folder']}"
                try:
                    predefined_metadata = {'type': doc['type']} if 'type' in doc else {}
                    result = load_documents_service.load_company_files(
                        company=self.company,
                        connector_config=connector_config,
                        predefined_metadata=predefined_metadata,
                        filters={"filename_contains": ".pdf"})
                    click.echo(f'folder {doc["folder"]}: {result} documents processed successfully.')
                except Exception as e:
                    logging.exception(e)
                    click.echo(f"Error: {str(e)}")

