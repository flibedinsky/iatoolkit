# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from repositories.models import DocumentType
from injector import inject
from repositories.database_manager import DatabaseManager
from common.exceptions import AppException
from sqlalchemy import func


class DocumentTypeRepo:
    @inject
    def __init__(self, db_manager: DatabaseManager):
        self.session = db_manager.get_session()

    def get_all_document_types(self):
        try:
            type_list = self.session.query(DocumentType).all()
            return type_list
        except Exception as e:
            raise AppException(AppException.ErrorType.DATABASE_ERROR,
                               'No se pudo buscar los tipos de documentos') from e

    def get_doc_type_id(self, name: str):
        try:
            doc_type = self.session.query(DocumentType).filter(func.lower(DocumentType.name) == func.lower(name)).first()
            if not doc_type:
                doc_type = self.session.query(DocumentType).filter_by(name='indefinido').first()
                if not doc_type:
                    raise AppException(AppException.ErrorType.DATABASE_ERROR,
                    'No existe el tipo de documento: indefinido')

            return doc_type.id
        except Exception as e:
            raise AppException(AppException.ErrorType.DATABASE_ERROR,
                               'No se pudo buscar los tipos de documentos') from e
