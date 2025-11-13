import pytest
from unittest.mock import patch, MagicMock
from iatoolkit.infra.llm_proxy import LLMProxy, LLMProvider
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.services.configuration_service import ConfigurationService


class TestLLMProxy:

    def setup_method(self):
        """Configuración común para las pruebas de LLMProxy."""
        self.util_mock = MagicMock()
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.util_mock.decrypt_key.side_effect = lambda x: f"decrypted_{x}"

        # Mocks para los clientes de los proveedores
        self.openai_patcher = patch('iatoolkit.infra.llm_proxy.OpenAI')
        self.gemini_patcher = patch('iatoolkit.infra.llm_proxy.genai')
        self.mock_openai_class = self.openai_patcher.start()
        self.mock_gemini_module = self.gemini_patcher.start()

        # Mocks para los adaptadores
        self.openai_adapter_patcher = patch('iatoolkit.infra.llm_proxy.OpenAIAdapter')
        self.gemini_adapter_patcher = patch('iatoolkit.infra.llm_proxy.GeminiAdapter')
        self.mock_openai_adapter_class = self.openai_adapter_patcher.start()
        self.mock_gemini_adapter_class = self.gemini_adapter_patcher.start()
        self.mock_openai_adapter_instance = MagicMock()
        self.mock_gemini_adapter_instance = MagicMock()
        self.mock_openai_adapter_class.return_value = self.mock_openai_adapter_instance
        self.mock_gemini_adapter_class.return_value = self.mock_gemini_adapter_instance

        # Mock de Compañía base
        self.company = MagicMock()
        self.company.short_name = 'test_company'
        self.company.name = 'Test Company'
        self.company.openai_api_key = None  # Asegurar que los atributos existen
        self.company.gemini_api_key = None  # aunque sean None

        # Instancia "fábrica" bajo prueba
        self.proxy_factory = LLMProxy(util=self.util_mock, configuration_service=self.mock_config_service)

    def teardown_method(self):
        patch.stopall()
        LLMProxy._clients_cache.clear()

    def test_create_openai_client_from_config(self):
        """Prueba que el cliente de OpenAI se crea usando la API key de la configuración."""
        self.mock_config_service.get_configuration.return_value = {'api-key': 'COMPANY_SPECIFIC_OPENAI_KEY'}
        with patch.dict('os.environ', {'COMPANY_SPECIFIC_OPENAI_KEY': 'key_from_config_env'}):
            self.proxy_factory._create_openai_client(self.company)
        self.mock_openai_class.assert_called_once_with(api_key='key_from_config_env')

    def test_create_openai_client_fallback_to_db_key(self):
        """Prueba que si no hay config, se usa la clave de la base de datos."""
        self.mock_config_service.get_configuration.return_value = None
        self.company.openai_api_key = 'db_key'
        self.proxy_factory._create_openai_client(self.company)
        self.util_mock.decrypt_key.assert_called_once_with('db_key')
        self.mock_openai_class.assert_called_once_with(api_key='decrypted_db_key')

    def test_create_openai_client_fallback_to_global_env(self):
        """Prueba que si no hay config ni clave en BD, se usa la variable de entorno global."""
        self.mock_config_service.get_configuration.return_value = None
        self.company.openai_api_key = None
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'global_key'}):
            self.proxy_factory._create_openai_client(self.company)
        self.mock_openai_class.assert_called_once_with(api_key='global_key')

    def test_create_for_company_raises_error_if_no_keys(self):
        """Prueba que el factory method lanza una excepción si no hay ninguna clave disponible por ningún medio."""
        self.mock_config_service.get_configuration.return_value = None
        self.company.openai_api_key = None
        self.company.gemini_api_key = None
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(IAToolkitException, match="no tiene configuradas API keys"):
                self.proxy_factory.create_for_company(self.company)

    def test_client_caching_works(self):
        """Prueba que los clientes se cachean y reutilizan entre llamadas."""
        self.mock_config_service.get_configuration.return_value = None
        self.company.openai_api_key = 'some_key'
        self.company.gemini_api_key = None

        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):  # Asegurar no fallback para gemini
            self.proxy_factory.create_for_company(self.company)
            self.proxy_factory.create_for_company(self.company)

        self.mock_openai_class.assert_called_once()

    def test_routing_to_correct_adapter(self):
        """Prueba el enrutamiento correcto hacia el adaptador adecuado."""
        self.util_mock.is_openai_model.return_value = True
        self.util_mock.is_gemini_model.return_value = False
        self.mock_config_service.get_configuration.return_value = None
        self.company.openai_api_key = 'some_key'  # Darle una clave para que pueda crear el cliente

        # Crear una instancia de proxy que tenga los adaptadores configurados
        work_proxy = self.proxy_factory.create_for_company(self.company)

        # Llamar a create_response en la instancia de trabajo
        work_proxy.create_response(model='gpt-4', input=[])

        self.mock_openai_adapter_instance.create_response.assert_called_once()
        self.mock_gemini_adapter_instance.create_response.assert_not_called()