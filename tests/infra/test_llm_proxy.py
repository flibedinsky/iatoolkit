import pytest
from unittest.mock import patch, MagicMock
from infra.llm_proxy import LLMProxy
from common.exceptions import AppException


class TestLLMProxy:

    def setup_method(self):
        """Configuración común para las pruebas de LLMProxy."""
        self.util_mock = MagicMock()
        self.util_mock.decrypt_key.side_effect = lambda x: f"decrypted_{x}"

        # Mocks para los clientes de los proveedores y sus adaptadores
        self.openai_patcher = patch('infra.llm_proxy.OpenAI')
        self.gemini_patcher = patch('infra.llm_proxy.genai')
        self.openai_adapter_patcher = patch('infra.llm_proxy.OpenAIAdapter')
        self.gemini_adapter_patcher = patch('infra.llm_proxy.GeminiAdapter')

        self.mock_openai_class = self.openai_patcher.start()
        self.mock_gemini_module = self.gemini_patcher.start()
        self.mock_openai_adapter_class = self.openai_adapter_patcher.start()
        self.mock_gemini_adapter_class = self.gemini_adapter_patcher.start()

        self.mock_openai_adapter_instance = MagicMock()
        self.mock_gemini_adapter_instance = MagicMock()
        self.mock_openai_adapter_class.return_value = self.mock_openai_adapter_instance
        self.mock_gemini_adapter_class.return_value = self.mock_gemini_adapter_instance

        # --- Mocks de Compañías usando MagicMock para evitar TypeError ---

        # Compañía con ambas claves
        self.company_both = MagicMock()
        self.company_both.short_name = 'comp_both'
        self.company_both.name = 'Both'
        self.company_both.llm_api_key = 'oa_key'
        self.company_both.gemini_api_key = 'g_key'

        # Compañía solo con OpenAI (la clave de gemini es None)
        self.company_openai = MagicMock()
        self.company_openai.short_name = 'comp_oa'
        self.company_openai.name = 'OpenAI'
        self.company_openai.llm_api_key = 'oa_key'

        # Compañía solo con Gemini (la clave de openai es None)
        self.company_gemini = MagicMock()
        self.company_gemini.short_name = 'comp_g'
        self.company_gemini.name = 'Gemini'

        # Compañía sin claves
        self.company_none = MagicMock()
        self.company_none.short_name = 'comp_none'
        self.company_none.name = 'None'
        self.company_none.llm_api_key = None

        patch.dict('os.environ', {'IATOOLKIT_OPENAI_API_KEY': 'fb_oa', 'GEMINI_API_KEY': 'fb_g'}).start()

        # Instancia "fábrica" bajo prueba
        self.proxy_factory = LLMProxy(util=self.util_mock)

    def teardown_method(self):
        patch.stopall()
        LLMProxy._clients_cache.clear()

    def test_create_for_company(self):
        """Prueba que el factory method crea un Proxy con ambos clientes."""
        proxy = self.proxy_factory.create_for_company(self.company_openai)

        self.mock_openai_class.assert_called_once_with(api_key='decrypted_oa_key')

        assert isinstance(proxy, LLMProxy)
        self.mock_openai_adapter_class.assert_called_once()
        self.mock_gemini_adapter_class.assert_called_once()
        assert proxy.openai_adapter is not None
        assert proxy.gemini_adapter is not None

    def test_create_for_company_raises_error_if_no_keys(self):
        """Prueba que el factory method lanza una excepción si no hay ninguna clave disponible."""
        with patch.dict('os.environ', {}, clear=True):
            # Usar una compañía que realmente no tenga los atributos
            company_truly_none = MagicMock()
            company_truly_none.llm_api_key = None

            with pytest.raises(AppException, match="no tiene configuradas API keys"):
                self.proxy_factory.create_for_company(company_truly_none)

    def test_client_caching_works(self):
        """Prueba que los clientes se cachean y reutilizan entre llamadas."""
        self.proxy_factory.create_for_company(self.company_openai)
        self.proxy_factory.create_for_company(self.company_openai)
        self.mock_openai_class.assert_called_once_with(api_key='decrypted_oa_key')

    def test_routing_to_openai_adapter(self):
        """Prueba el enrutamiento correcto hacia el adaptador de OpenAI."""
        self.util_mock.is_openai_model.return_value = True
        self.util_mock.is_gemini_model.return_value = False

        proxy = self.proxy_factory.create_for_company(self.company_openai)

        # El método create_response no está definido en el MagicMock `proxy`,
        # así que llamamos al método real en la instancia de fábrica para obtener una instancia real
        work_proxy = self.proxy_factory.create_for_company(self.company_openai)
        work_proxy.create_response(model='gpt-4', input=[])

        self.mock_openai_adapter_instance.create_response.assert_called_once()
        self.mock_gemini_adapter_instance.create_response.assert_not_called()

    def test_routing_to_gemini_adapter(self):
        """Prueba el enrutamiento correcto hacia el adaptador de OpenAI."""
        self.util_mock.is_openai_model.return_value = False
        self.util_mock.is_gemini_model.return_value = True

        proxy = self.proxy_factory.create_for_company(self.company_openai)

        # El método create_response no está definido en el MagicMock `proxy`,
        # así que llamamos al método real en la instancia de fábrica para obtener una instancia real
        work_proxy = self.proxy_factory.create_for_company(self.company_gemini)
        work_proxy.create_response(model='gemini', input=[])

        self.mock_gemini_adapter_instance.create_response.assert_called_once()
        self.mock_openai_adapter_instance.create_response.assert_not_called()