# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from services.excel_service import ExcelService
from common.util import Utility


class TestExcelService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = Flask(__name__)
        self.app.testing = True

        # Create real temporary directory structure
        self.temp_dir_base = tempfile.mkdtemp()
        self.app.root_path = self.temp_dir_base
        self.temp_dir = os.path.join(self.temp_dir_base, 'static', 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)

        # Mocks of services
        self.util = MagicMock(spec=Utility)
        self.excel_service = ExcelService(util=self.util)

        yield

        # Cleanup after test
        shutil.rmtree(self.temp_dir_base)

    def create_test_file(self, filename, content=b'test content'):
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path

    def test_validate_file_access_valid_file(self):
        filename = 'valid_file.xlsx'
        self.create_test_file(filename)

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is None

    def test_validate_file_access_path_traversal_dotdot(self):
        filename = '../../../etc/passwd'

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Nombre de archivo inválido'

    def test_validate_file_access_path_traversal_absolute_unix(self):
        filename = '/etc/passwd'

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Nombre de archivo inválido'

    def test_validate_file_access_path_traversal_backslash(self):
        filename = 'folder\\..\\sensitive_file.txt'

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Nombre de archivo inválido'

    def test_validate_file_access_file_not_found(self):
        filename = 'non_existent_file.xlsx'

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Archivo no encontrado'

    def test_validate_file_access_is_directory(self):
        dirname = 'test_directory'
        dir_path = os.path.join(self.temp_dir, dirname)
        os.makedirs(dir_path)

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(dirname)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'La ruta no corresponde a un archivo'

    def test_validate_file_access_exception_handling(self):
        filename = 'test_file.xlsx'

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                with patch('services.excel_service.os.path.exists', side_effect=Exception("Test exception")):
                    result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Error validando archivo'

    def test_validate_file_access_logs_exception(self):
        filename = 'test_file.xlsx'

        with patch('services.excel_service.logging') as mock_logging:
            with patch('services.excel_service.os.path.exists', side_effect=Exception("Test exception")):
                with self.app.app_context():
                    with patch('services.excel_service.current_app') as mock_current_app:
                        mock_current_app.root_path = self.temp_dir_base
                        self.excel_service.validate_file_access(filename)

        mock_logging.error.assert_called_once()
        error_msg = mock_logging.error.call_args[0][0]
        assert 'Error validando acceso al archivo test_file.xlsx' in error_msg
        assert 'Test exception' in error_msg

    def test_validate_file_access_various_valid_filenames(self):
        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base

                valid_filenames = [
                    'simple.xlsx',
                    'file_with_underscores.xlsx',
                    'file-with-dashes.xlsx',
                    'file with spaces.xlsx',
                    'file123.xlsx',
                    'UPPERCASE.XLSX',
                    'file.with.dots.xlsx'
                ]

                for filename in valid_filenames:
                    self.create_test_file(filename)
                    result = self.excel_service.validate_file_access(filename)
                    assert result is None, f"Filename '{filename}' should be valid"

    def test_validate_file_access_various_invalid_filenames(self):
        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base

                invalid_filenames = [
                    '../file.xlsx',
                    '../../file.xlsx',
                    '/absolute/path/file.xlsx',
                    'folder\\file.xlsx',
                    '..\\file.xlsx',
                    'file..xlsx/../other.xlsx',
                    '/etc/passwd',
                    'C:\\Windows\\System32\\config'
                ]

                for filename in invalid_filenames:
                    result = self.excel_service.validate_file_access(filename)
                    assert result is not None, f"Filename '{filename}' should be invalid"
                    data = result.get_json()
                    assert data['error'] == 'Nombre de archivo inválido'

    def test_validate_file_access_empty_filename(self):
        filename = ''

        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Nombre de archivo inválido'

    def test_validate_file_access_none_filename(self):
        with self.app.app_context():
            with patch('services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(None)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'Nombre de archivo inválido'
