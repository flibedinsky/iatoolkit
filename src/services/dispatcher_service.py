# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from common.exceptions import IAToolkitException
from services.prompt_manager_service import PromptService
from repositories.llm_query_repo import LLMQueryRepo
from repositories.models import Company, Function
from services.excel_service import ExcelService
from services.mail_service import MailService
from iatoolkit.base_company import BaseCompany
from common.util import Utility
from injector import inject
import importlib
import pkgutil
import inspect
import logging
import os


class Dispatcher:
    @inject
    def __init__(self,
                 prompt_service: PromptService,
                 llmquery_repo: LLMQueryRepo,
                 util: Utility,
                 excel_service: ExcelService,
                 mail_service: MailService):
        self.prompt_service = prompt_service
        self.llmquery_repo = llmquery_repo
        self.util = util
        self.excel_service = excel_service
        self.mail_service = mail_service
        self.system_functions = _FUNCTION_LIST
        self.system_prompts = _SYSTEM_PROMPT

        # automatic discovery of company classes
        self.company_classes = self._discover_company_classes()

        self.tool_handlers = {
            "iat_generate_excel": self.excel_service.excel_generator,
            "iat_send_email": self.mail_service.send_mail,
        }

    def init_db(self):
        # create system functions
        for function in self.system_functions:
            self.llmquery_repo.create_or_update_function(
                Function(
                    company_id=None,
                    system_function=True,
                    name=function['function_name'],
                    description= function['description'],
                    parameters=function['parameters']
                )
            )

            # create the system prompts
            i = 1
            for prompt in self.system_prompts:
                self.prompt_service.create_prompt(
                    prompt_name=prompt['name'],
                    description=prompt['description'],
                    order=1,
                    is_system_prompt=True
                )
                i += 1

        # initialize the database for every company class
        for company in self.company_classes.values():
            print(f'inicializando clase: {company.__class__.__name__}')
            company.init_db()

    def start_execution(self):
        for company in self.company_classes.values():
            logging.info(f'init execution for company: {company.__class__.__name__}')
            company.start_execution()

        return True

    def dispatch(self, company_name: str, action: str, **kwargs) -> str:
        if company_name not in self.company_classes:
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Empresa no configurada: {company_name}")

        # check if action is a system function
        if action in self.tool_handlers:
            return  self.tool_handlers[action](**kwargs)

        company_instance = self.company_classes[company_name]
        try:
            return company_instance.handle_request(action, **kwargs)
        except IAToolkitException as e:
            # Si ya es una IAToolkitException, la relanzamos para preservar el tipo de error original.
            raise e

        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Error en function call '{action}': {str(e)}") from e

    def get_company_context(self, company_name: str, **kwargs) -> str:
        if company_name not in self.company_classes:
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Empresa no configurada: {company_name}")

        company_context = ''

        # read the company context from this list of markdown files,
        # company brief, credits, operation description, etc.
        context_dir = os.path.join(os.getcwd(), f'companies/{company_name}/context')
        context_files = self.util.get_files_by_extension(context_dir, '.md', return_extension=True)
        for file in context_files:
            filepath = os.path.join(context_dir, file)
            company_context += self.util.load_markdown_context(filepath)

        # add the schemas for every table or function call responses
        schema_dir = os.path.join(os.getcwd(), f'companies/{company_name}/schema')
        schema_files = self.util.get_files_by_extension(schema_dir, '.yaml', return_extension=True)
        for file in schema_files:
            schema_name = file.split('_')[0]
            filepath = os.path.join(schema_dir, file)
            company_context += self.util.generate_context_for_schema(schema_name, filepath)

        company_instance = self.company_classes[company_name]
        try:
            return company_context + company_instance.get_company_context(**kwargs)
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Error en get_company_context de {company_name}: {str(e)}") from e

    def get_company_services(self, company: Company) -> list[dict]:
        # create the syntax with openai response syntax, for the company function list
        tools = []
        functions = self.llmquery_repo.get_company_functions(company)

        for function in functions:
            # make sure is always on
            function.parameters["additionalProperties"] = False

            ai_tool = {
                "type": "function",
                "name": function.name,
                "description": function.description,
                "parameters": function.parameters,
                "strict": True
            }
            tools.append(ai_tool)
        return tools

    def get_user_info(self, company_name: str, **kwargs) -> dict:
        if company_name not in self.company_classes:
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Empresa no configurada: {company_name}")

        company_instance = self.company_classes[company_name]
        try:
            return company_instance.get_user_info(**kwargs)
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Error en get_user_info de {company_name}: {str(e)}") from e


    def get_metadata_from_filename(self, company_name: str, filename: str) -> dict:
        if company_name not in self.company_classes:
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Empresa no configurada: {company_name}")

        company_instance = self.company_classes[company_name]
        try:
            return company_instance.get_metadata_from_filename(filename)
        except Exception as e:
            logging.exception(e)
            raise IAToolkitException(IAToolkitException.ErrorType.EXTERNAL_SOURCE_ERROR,
                               f"Error en get_metadata_from_filename de {company_name}: {str(e)}") from e

    def _discover_company_classes(self) -> dict:
        """
        Descubre dinámicamente todas las clases de empresa que heredan de BaseCompany
        """
        company_classes = {}

        try:
            # Importar el paquete companies
            import companies
            companies_package = companies

            # Recorrer todos los módulos en el paquete companies
            for importer, modname, ispkg in pkgutil.iter_modules(companies_package.__path__):
                if ispkg:  # Si es un subpaquete (como companies.maxxa)
                    continue

                try:
                    # Importar el módulo
                    module_name = f"companies.{modname}"
                    module = importlib.import_module(module_name)

                    # Buscar clases que hereden de BaseCompany
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (obj != BaseCompany and
                                issubclass(obj, BaseCompany) and
                                obj.__module__ == module_name):

                            # Crear instancia usando el inyector
                            try:
                                # Obtener la instancia del inyector
                                from injector import Injector
                                injector = Injector()
                                company_instance = injector.get(obj)

                                # Usar el nombre de la clase en minúsculas como key
                                company_key = name.lower()
                                company_classes[company_key] = company_instance

                                logging.info(f"Empresa registrada dinámicamente: {company_key} -> {name}")

                            except Exception as e:
                                logging.warning(f"No se pudo crear instancia de {name}: {e}")

                except ImportError as e:
                    logging.warning(f"No se pudo importar módulo {modname}: {e}")

        except Exception as e:
            logging.error(f"Error en autodescubrimiento de empresas: {e}")

        return company_classes


# iatoolkit system prompts
_SYSTEM_PROMPT = [
    {'name': 'query_main', 'description':'main prompt de iatoolkit'},
    {'name': 'format_styles', 'description':'formatos y estilos de salida'},
    {'name': 'sql_rules', 'description':'instrucciones para generar sql'}
]


# iatoolkit  function calls
_FUNCTION_LIST = [
    {
        "name": "iat_generate_excel",
        "description": "Generador de Excel."
                    "Genera un archivo Excel (.xlsx) a partir de una lista de diccionarios. "
                    "Cada diccionario representa una fila del archivo. "
                    "el archivo se guarda en directorio de descargas."
                    "retorna diccionario con filename, attachment_token (para enviar archivo por mail)"
                    "content_type y download_link",
        "function_name": "iat_generate_excel",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Nombre del archivo de salida (ejemplo: 'reporte.xlsx')",
                    "pattern": "^.+\\.xlsx?$"
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Nombre de la hoja dentro del Excel",
                    "minLength": 1
                },
                "data": {
                    "type": "array",
                    "description": "Lista de diccionarios. Cada diccionario representa una fila.",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "boolean"},
                                {"type": "null"},
                                {
                                    "type": "string",
                                    "format": "date"
                                }
                            ]
                        }
                    }
                }
            },
            "required": ["filename", "sheet_name", "data"]
        }
    },
    {
        'name': 'Envio de mails',
         'description':  "iatoolkit mail system. "        
            "envia mails cuando un usuario lo solicita."
            "Si no te indican quien envia el correo utiliza la dirección iatoolkit@iatoolkit.com",
         'function_name': "iat_send_email",
         'parameters': {
            "type": "object",
            "properties": {
                "from_email": {"type": "string","description": "dirección de correo electrónico  que esta enviando el email."},
                "recipient": {"type": "string", "description": "email del destinatario"},
                "subject": {"type": "string", "description": "asunto del email"},
                "body": {"type": "string", "description": "HTML del email"},
                "attachments": {
                    "type": "array",
                    "description": "Lista de archivos adjuntos codificados en base64",
                    "items": {
                      "type": "object",
                      "properties": {
                        "filename": {
                          "type": "string",
                          "description": "Nombre del archivo con su extensión (ej. informe.pdf)"
                        },
                        "content": {
                          "type": "string",
                          "description": "Contenido del archivo en b64."
                        },
                        "attachment_token": {
                          "type": "string",
                          "description": "token para descargar el archivo."
                        }
                      },
                      "required": ["filename", "content", "attachment_token"],
                      "additionalProperties": False
                    }
                }
            },
            "required": ["from_email","recipient", "subject", "body", "attachments"]
        }
     }
]
