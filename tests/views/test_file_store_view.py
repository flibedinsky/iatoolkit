# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from flask import Flask
from views.file_store_view import FileStoreView
from services.load_documents_service import LoadDocumentsService
from repositories.profile_repo import ProfileRepo
import base64


class TestFileStoreView:

    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()

        # Mock the services
        self.mock_doc_service = MagicMock(spec=LoadDocumentsService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)

        # Instantiate the view with mocked services
        self.file_store_view = FileStoreView.as_view("load",
                                                    doc_service=self.mock_doc_service,
                                                    profile_repo=self.mock_profile_repo)
        self.app.add_url_rule('/load', view_func=self.file_store_view, methods=["POST"])

    @pytest.mark.parametrize("missing_field", ["company", "filename", "content"])
    def test_post_when_missing_required_fields(self, missing_field):
        payload = {
            "company": "test_company",
            "filename": "test_file.txt",
            "content": base64.b64encode(b"test content").decode('utf-8'),
            "metadata": {"key": "value"}
        }
        payload.pop(missing_field)

        response = self.client.post('/load', json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": f"El campo {missing_field} es requerido"
        }

        self.mock_doc_service.load_file.assert_not_called()

    def test_post_when_company_not_found(self):
        # Mock the profile repo to return None for the company
        self.mock_profile_repo.get_company_by_short_name.return_value = None

        payload = {
            "company": "nonexistent_company",
            "filename": "test_file.txt",
            "content": base64.b64encode(b"test content").decode('utf-8'),
            "metadata": {"key": "value"}
        }

        response = self.client.post('/load', json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": "La empresa nonexistent_company no existe"
        }

        self.mock_profile_repo.get_company_by_short_name.assert_called_once_with("nonexistent_company")
        self.mock_doc_service.load_file.assert_not_called()

    def test_post_when_internal_exception_error(self):
        # Mock the profile repo to return a company
        mock_company = MagicMock()
        self.mock_profile_repo.get_company_by_short_name.return_value = mock_company

        # Mock the doc service to raise an exception
        self.mock_doc_service.load_file.side_effect = Exception("Internal Error")

        payload = {
            "company": "test_company",
            "filename": "test_file.txt",
            "content": base64.b64encode(b"test content").decode('utf-8'),
            "metadata": {"key": "value"}
        }

        response = self.client.post('/load', json=payload)

        assert response.status_code == 500
        response_json = response.get_json()
        assert response_json is not None, "Expected JSON response, got None"

        assert "error" in response_json
        assert response_json["error"] == "Internal Error"

        self.mock_profile_repo.get_company_by_short_name.assert_called_once_with("test_company")
        self.mock_doc_service.load_file.assert_called_once()

    def test_post_when_successful_file_storage(self):
        # Mock the profile repo to return a company
        mock_company = MagicMock()
        self.mock_profile_repo.get_company_by_short_name.return_value = mock_company

        # Mock the document returned by the service
        mock_document = MagicMock()
        mock_document.id = 123
        self.mock_doc_service.load_file.return_value = mock_document

        payload = {
            "company": "test_company",
            "filename": "test_file.txt",
            "content": base64.b64encode(b"test content").decode('utf-8'),
            "metadata": {"key": "value"}
        }

        response = self.client.post('/load', json=payload)

        assert response.status_code == 200
        assert response.get_json() == {
            "document_id": 123
        }

        self.mock_profile_repo.get_company_by_short_name.assert_called_once_with("test_company")
        self.mock_doc_service.load_file.assert_called_once_with(
            filename="test_file.txt",
            content=b"test content",
            company=mock_company,
            metadata={"key": "value"}
        )
