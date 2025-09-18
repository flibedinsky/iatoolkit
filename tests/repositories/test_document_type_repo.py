# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from repositories.models import DocumentType
from repositories.document_type_repo import DocumentTypeRepo
from common.exceptions import AppException
from sqlalchemy.exc import SQLAlchemyError


class TestDocumentTypeRepo:
    def setup_method(self):
        # Mock del DatabaseManager
        self.mock_db_manager = MagicMock()
        self.session = self.mock_db_manager.get_session()

        # Inicializar DocumentTypeRepo con el DatabaseManager simulado
        self.repo = DocumentTypeRepo(self.mock_db_manager)

    def test_get_all_document_types_when_db_error(self):
        # Simular un error al consultar los tipos de documentos
        self.session.query.side_effect = Exception("Database error")

        # Probar la obtención de tipos con excepción
        with pytest.raises(AppException) as excinfo:
            self.repo.get_all_document_types()

        # Validar que la excepción es la esperada
        assert excinfo.value.error_type == AppException.ErrorType.DATABASE_ERROR

    def test_get_all_document_types_when_success(self):
        # Configurar el mock para retornar una lista de tipos de documentos
        mock_types = [
            DocumentType(id=1, name="Type A"),
            DocumentType(id=2, name="Type B")
        ]
        self.session.query().all.return_value = mock_types

        # Llamar al método
        result = self.repo.get_all_document_types()

        # Validar los resultados
        assert len(result) == 2
        assert result[0].name == "Type A"

    def test_get_doc_type_id_when_db_error(self):
        self.session.query.side_effect = SQLAlchemyError("Error simulado")
        with pytest.raises(AppException) as excinfo:
            self.repo.get_doc_type_id('escritura')

        # Validar que la excepción es la esperada
        assert excinfo.value.error_type == AppException.ErrorType.DATABASE_ERROR

    def test_get_doc_type_id_when_not_exist(self):
        self.session.query.return_value.filter.return_value.first.return_value = None
        self.session.query.return_value.filter_by.return_value.first.return_value = None
        with pytest.raises(AppException) as excinfo:
            self.repo.get_doc_type_id('escritura')

        # Validar que la excepción es la esperada
        assert excinfo.value.error_type == AppException.ErrorType.DATABASE_ERROR

    def test_get_doc_type_id_when_found_by_name(self):
        mock_doc_type = DocumentType(id=1, name='escritura')
        self.session.query.return_value.filter.return_value.first.return_value = mock_doc_type

        result = self.repo.get_doc_type_id('escritura')

        # Validar que el resultado es el ID correcto
        assert result == 1

    def test_get_doc_type_id_when_not_found_but_default_exists(self):
        self.session.query.return_value.filter.return_value.first.return_value = None
        mock_default_doc_type = DocumentType(id=99, name='indefinido')
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_default_doc_type

        result = self.repo.get_doc_type_id('escritura')

        # Validar que el resultado es el ID del tipo "indefinido"
        assert result == 99

