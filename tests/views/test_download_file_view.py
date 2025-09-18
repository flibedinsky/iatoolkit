# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, jsonify

from common.auth import IAuthentication
from repositories.models import Company
from services.excel_service import ExcelService
from services.profile_service import ProfileService
from views.download_file_view import DownloadFileView


class TestDownloadFileView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = Flask(__name__)
        self.app.testing = True

        # Create a real temporary directory for static/temp
        self.temp_dir_base = tempfile.mkdtemp()
        self.app.root_path = self.temp_dir_base
        temp_dir_path = os.path.join(self.app.root_path, 'static', 'temp')
        os.makedirs(temp_dir_path)

        # Create a real test file
        self.test_filename = 'test_file.xlsx'
        self.test_file_path = os.path.join(temp_dir_path, self.test_filename)
        self.test_content = b'test file content'
        with open(self.test_file_path, 'wb') as f:
            f.write(self.test_content)

        # Mocks of services
        self.iauthentication = MagicMock(spec=IAuthentication)
        self.profile_service = MagicMock(spec=ProfileService)
        self.excel_service = MagicMock(spec=ExcelService)

        # Default mock configuration for successful case
        self.iauthentication.verify.return_value = {'success': True}
        self.test_company = Company(id=1, name="Test Company", short_name="test_company")
        self.profile_service.get_company_by_short_name.return_value = self.test_company
        self.excel_service.validate_file_access.return_value = None

        # Inject mocks and register the route
        view = DownloadFileView.as_view(
            'download_file',
            iauthentication=self.iauthentication,
            profile_service=self.profile_service,
            excel_service=self.excel_service,
        )
        self.app.add_url_rule(
            '/<string:company_short_name>/<string:external_user_id>/download-file/<path:filename>',
            view_func=view
        )

        self.client = self.app.test_client()

        yield

        # Cleanup after test
        shutil.rmtree(self.temp_dir_base)

    def test_successful_download(self):
        with self.app.app_context():
            response = self.client.get(f'/test_company/user_123/download-file/{self.test_filename}')

        assert response.status_code == 200
        assert response.data == self.test_content
        assert response.headers['Content-Disposition'] == f'attachment; filename={self.test_filename}'

        self.iauthentication.verify.assert_called_once_with('test_company', body_external_user_id='user_123')
        self.profile_service.get_company_by_short_name.assert_called_once_with('test_company')
        self.excel_service.validate_file_access.assert_called_once_with(self.test_filename)

    def test_missing_external_user_id(self):
        # Test with empty external_user_id
        with self.app.app_context():
            response = self.client.get('/test_company//download-file/file.xlsx')

        view = DownloadFileView(
            iauthentication=self.iauthentication,
            profile_service=self.profile_service,
            excel_service=self.excel_service
        )

        with self.app.test_request_context():
            response = view.get('test_company', '', 'file.xlsx')

        assert response[1] == 400
        data = response[0].get_json()
        assert data['error'] == 'Falta external_user_id'

    def test_authentication_failure(self):
        self.iauthentication.verify.return_value = {'success': False, 'error': 'Token inválido'}

        with self.app.app_context():
            response = self.client.get(f'/test_company/user_123/download-file/{self.test_filename}')

        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Token inválido'

    def test_company_not_found(self):
        self.profile_service.get_company_by_short_name.return_value = None

        with self.app.app_context():
            response = self.client.get(f'/test_company/user_123/download-file/{self.test_filename}')

        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Empresa no encontrada'

    def test_file_validation_error(self):
        with self.app.app_context():
            self.excel_service.validate_file_access.return_value = (jsonify({"error": "Acceso denegado"}), 403)
            response = self.client.get('/test_company/user_123/download-file/unauthorized_file.xlsx')

        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'Acceso denegado'

    def test_file_not_found_on_disk(self):
        with self.app.app_context():
            response = self.client.get('/test_company/user_123/download-file/non_existent_file.xlsx')

        assert response.status_code == 500
        data = response.get_json()
        assert data['error'] == 'Error descargando archivo'

    @patch('views.download_file_view.logging')
    def test_logging_on_success_and_error(self, mock_logging):
        with self.app.app_context():
            # Success case
            self.client.get(f'/test_company/user_123/download-file/{self.test_filename}')
            mock_logging.info.assert_called_with(f'Archivo descargado via API: {self.test_filename}')

            # Error case
            self.client.get('/test_company/user_123/download-file/non_existent_file.xlsx')
            assert mock_logging.error.call_count == 1
            args, _ = mock_logging.error.call_args
            assert 'Error descargando archivo non_existent_file.xlsx' in args[0]
