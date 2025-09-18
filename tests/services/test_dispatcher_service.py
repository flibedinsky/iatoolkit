# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from services.dispatcher_service import Dispatcher
from common.exceptions import AppException
from repositories.llm_query_repo import LLMQueryRepo
from services.excel_service import ExcelService
from services.mail_service import MailService
from common.util import Utility


class TestDispatcher:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura los mocks para las empresas y el Dispatcher."""
        # Mocks para los servicios
        self.mock_prompt_manager = MagicMock()
        self.mock_llm_query_repo = MagicMock(spec=LLMQueryRepo)
        self.excel_service = MagicMock(spec=ExcelService)
        self.mail_service = MagicMock(spec=MailService)
        self.util = MagicMock(spec=Utility)

        # Mock para las empresas que se descubrirán dinámicamente
        self.mock_maxxa = MagicMock()
        self.mock_maxxa.handle_request.return_value = {"result": "maxxa_response"}
        self.mock_maxxa.get_company_context.return_value = "Company Context Maxxa"
        self.mock_maxxa.start_execution.return_value = True

        # Mock del método _discover_company_classes para controlar las empresas encontradas
        with patch.object(Dispatcher, '_discover_company_classes') as mock_discover:
            mock_discover.return_value = {"maxxa": self.mock_maxxa}

            # Dispatcher inicializado con los mocks
            self.dispatcher = Dispatcher(
                prompt_service=self.mock_prompt_manager,
                llmquery_repo=self.mock_llm_query_repo,
                util=self.util,
                excel_service=self.excel_service,
                mail_service=self.mail_service
            )

    def test_init_db_calls_init_db_on_each_company(self):
        """Test que init_db llama a init_db de cada empresa."""
        self.dispatcher.init_db()
        self.mock_maxxa.init_db.assert_called_once()

    def test_dispatch_maxxa(self):
        """Test que dispatch funciona correctamente para una empresa válida."""
        result = self.dispatcher.dispatch("maxxa", "finantial_data", key='a value')

        self.mock_maxxa.handle_request.assert_called_once_with("finantial_data", key='a value')
        assert result == {"result": "maxxa_response"}

    def test_dispatch_invalid_company(self):
        """Test que dispatch lanza excepción para empresa no configurada."""
        with pytest.raises(AppException) as excinfo:
            self.dispatcher.dispatch("invalid_company", "some_tag")

        # Validar que se lanza la excepción correcta
        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Empresa no configurada: invalid_company" in str(excinfo.value)

    def test_dispatch_method_exception(self):
        """Valida que el dispatcher maneje excepciones lanzadas por las empresas."""
        # Configurar un mock para arrojar excepción
        self.mock_maxxa.handle_request.side_effect = Exception("Method error")

        with pytest.raises(AppException) as excinfo:
            self.dispatcher.dispatch("maxxa", "finantial_data")

        # Validar que se captura y transforma la excepción
        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Error en function call 'finantial_data': Method error" in str(excinfo.value)

    def test_dispatch_system_function(self):
        """Test que dispatch maneja correctamente las funciones del sistema."""
        # Mock del excel_service
        self.excel_service.excel_generator.return_value = {"file": "test.xlsx"}

        result = self.dispatcher.dispatch("maxxa", "iat_generate_excel", filename="test.xlsx")

        # Verificar que se llamó al servicio correcto y no a la empresa
        self.excel_service.excel_generator.assert_called_once_with(filename="test.xlsx")
        self.mock_maxxa.handle_request.assert_not_called()
        assert result == {"file": "test.xlsx"}

    @patch('os.path.join')
    @patch('os.getcwd')
    def test_get_company_context(self, mock_getcwd, mock_join):
        """Test que get_company_context funciona correctamente."""
        # Mock de las rutas y archivos
        mock_getcwd.return_value = "/test/path"
        mock_join.return_value = "/test/path/companies/maxxa/context"

        self.util.get_files_by_extension.return_value = []

        params = {"param1": "value1"}
        result = self.dispatcher.get_company_context("maxxa", **params)

        # Verificar que se llamó al método de la empresa
        self.mock_maxxa.get_company_context.assert_called_once_with(**params)
        assert "Company Context Maxxa" in result

    def test_get_company_context_invalid_company(self):
        """Test que get_company_context lanza excepción para empresa no configurada."""
        with pytest.raises(AppException) as excinfo:
            self.dispatcher.get_company_context("invalid_company")

        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Empresa no configurada: invalid_company" in str(excinfo.value)

    def test_start_execution_when_ok(self):
        """Test que start_execution funciona correctamente."""
        result = self.dispatcher.start_execution()

        assert result == True
        self.mock_maxxa.start_execution.assert_called_once()

    def test_start_execution_when_exception(self):
        """Test que start_execution propaga excepciones de las empresas."""
        self.mock_maxxa.start_execution.side_effect = Exception('an error')

        with pytest.raises(Exception) as excinfo:
            self.dispatcher.start_execution()

        assert str(excinfo.value) == 'an error'

    def test_get_user_info(self):
        """Test que get_user_info funciona correctamente."""
        expected_result = {"user_id": "123", "name": "Test User"}
        self.mock_maxxa.get_user_info.return_value = expected_result

        params = {"user_id": "123"}
        result = self.dispatcher.get_user_info("maxxa", **params)

        self.mock_maxxa.get_user_info.assert_called_once_with(**params)
        assert result == expected_result

    def test_get_user_info_invalid_company(self):
        """Test que get_user_info lanza excepción para empresa no configurada."""
        with pytest.raises(AppException) as excinfo:
            self.dispatcher.get_user_info("invalid_company")

        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Empresa no configurada: invalid_company" in str(excinfo.value)

    def test_get_metadata_from_filename(self):
        """Test que get_metadata_from_filename funciona correctamente."""
        expected_result = {"filename": "test.pdf", "metadata": "data"}
        self.mock_maxxa.get_metadata_from_filename.return_value = expected_result

        result = self.dispatcher.get_metadata_from_filename("maxxa", "test.pdf")

        self.mock_maxxa.get_metadata_from_filename.assert_called_once_with("test.pdf")
        assert result == expected_result

    def test_get_metadata_from_filename_invalid_company(self):
        """Test que get_metadata_from_filename lanza excepción para empresa no configurada."""
        with pytest.raises(AppException) as excinfo:
            self.dispatcher.get_metadata_from_filename("invalid_company", "test.pdf")

        assert excinfo.value.error_type == AppException.ErrorType.EXTERNAL_SOURCE_ERROR
        assert "Empresa no configurada: invalid_company" in str(excinfo.value)

    @patch.object(Dispatcher, '_discover_company_classes')
    def test_discover_company_classes_empty(self, mock_discover):
        """Test que el dispatcher funciona correctamente cuando no encuentra empresas."""
        mock_discover.return_value = {}

        dispatcher = Dispatcher(
            prompt_service=self.mock_prompt_manager,
            llmquery_repo=self.mock_llm_query_repo,
            util=self.util,
            excel_service=self.excel_service,
            mail_service=self.mail_service
        )

        # Verificar que no hay empresas registradas
        assert len(dispatcher.company_classes) == 0

        # Verificar que dispatch falla para cualquier empresa
        with pytest.raises(AppException) as excinfo:
            dispatcher.dispatch("any_company", "some_action")

        assert "Empresa no configurada: any_company" in str(excinfo.value)

    def test_get_company_services(self):
        """Test que get_company_services funciona correctamente."""
        from repositories.models import Company

        # Mock de company y functions
        mock_company = MagicMock(spec=Company)
        mock_function = MagicMock()
        mock_function.name = "test_function"
        mock_function.description = "Test function"
        mock_function.parameters = {"type": "object", "properties": {}}

        self.mock_llm_query_repo.get_company_functions.return_value = [mock_function]

        result = self.dispatcher.get_company_services(mock_company)

        # Verificar la estructura del resultado
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "test_function"
        assert result[0]["description"] == "Test function"
        assert result[0]["parameters"]["additionalProperties"] == False
        assert result[0]["strict"] == True