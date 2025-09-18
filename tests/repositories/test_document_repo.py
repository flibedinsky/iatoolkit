# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from repositories.models import Document, Company
from repositories.document_repo import DocumentRepo
from common.exceptions import AppException
import base64


class TestDocumentRepo:
    def setup_method(self):
        # Mock the DatabaseManager
        self.mock_db_manager = MagicMock()
        self.session = self.mock_db_manager.get_session()

        # Initialize DocumentRepo with the mocked DatabaseManager
        self.repo = DocumentRepo(self.mock_db_manager)
        self.mock_document = Document(company_id=1,
                                 filename='test.txt',
                                 content='123',
                                 content_b64=base64.b64encode('123'.encode('utf-8')).decode('utf-8'),
                                 meta={'repertorio_id': 10})
        self.mock_company = Company(name='company')


    def test_insert_when_ok(self):
        self.repo.insert(self.mock_document)

        # Assert
        self.session.add.assert_called()
        self.session.commit.assert_called()

    def test_get_missing_company(self):
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            self.repo.get(None, filename="test_file.txt")

        assert exc_info.value.error_type == AppException.ErrorType.PARAM_NOT_FILLED

    def test_get_document_by_filename(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = self.mock_document

        # Act
        result = self.repo.get(self.mock_company, filename="test_file.txt")

        # Assert
        assert result == self.mock_document
        self.session.query.assert_called()

    def test_get_by_id_when_id_is_none(self):
        result = self.repo.get_by_id(0)

        assert result is None
        self.session.query.assert_not_called()

    def test_get_by_id_when_document_not_found(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = None

        result = self.repo.get_by_id(999)

        assert result is None
        self.session.query.assert_called()

    def test_get_by_id_when_document_exists(self):
        self.session.query.return_value.filter_by.return_value.first.return_value = self.mock_document

        result = self.repo.get_by_id(1)

        assert result == self.mock_document
        self.session.query.assert_called()


