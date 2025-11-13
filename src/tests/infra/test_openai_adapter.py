import pytest
from unittest.mock import Mock, patch

from iatoolkit.infra.llm_proxy import LLMProxy
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.infra.llm_response import LLMResponse, Usage


class TestLLMProxy:
    """Tests para la clase LLMProxy."""

    def setup_method(self):
        """Configura el entorno de prueba para cada método."""
        # Parcheamos las clases de los adaptadores en el módulo donde se utilizan (llm_proxy)
        self.openai_patcher = patch('iatoolkit.infra.llm_proxy.OpenAIAdapter', autospec=True)
        self.gemini_patcher = patch('iatoolkit.infra.llm_proxy.GeminiAdapter', autospec=True)

        # Iniciamos los patchers
        self.MockOpenAIAdapter = self.openai_patcher.start()
        self.MockGeminiAdapter = self.gemini_patcher.start()

        # Mocks para los clientes de las APIs
        self.mock_openai_client = Mock()
        self.mock_gemini_client = Mock()

        # Instanciamos LLMProxy. Esto usará las clases de adaptadores mockeadas.
        self.util_mock = Mock()
        self.proxy = LLMProxy(
            openai_client=self.mock_openai_client,
            gemini_client=self.mock_gemini_client,
            util=self.util_mock,
            configuration_service=self.mock_gemini_client
        )

        # Obtenemos una referencia a las instancias mockeadas que LLMProxy crea internamente
        self.mock_openai_adapter_instance = self.proxy.openai_adapter
        self.mock_gemini_adapter_instance = self.proxy.gemini_adapter

    def teardown_method(self):
        """Limpia el entorno de prueba después de cada método."""
        self.openai_patcher.stop()
        self.gemini_patcher.stop()

    def test_create_response_routes_to_openai(self):
        """
        Prueba que create_response enruta correctamente al adaptador de OpenAI
        para un modelo de OpenAI.
        """
        model = "gpt-4"
        input_data = [{"role": "user", "content": "Hola"}]
        mock_usage = Usage(input_tokens=10, output_tokens=10, total_tokens=20)
        mock_response = LLMResponse(id="resp-123", model=model, status="completed", output_text="Hola!", output=[], usage=mock_usage)
        self.mock_openai_adapter_instance.create_response.return_value = mock_response
        self.util_mock.is_openai_model.return_value = True
        response = self.proxy.create_response(model=model, input=input_data)

        self.mock_openai_adapter_instance.create_response.assert_called_once_with(
            model=model,
            input=input_data
        )
        self.mock_gemini_adapter_instance.create_response.assert_not_called()
        assert response == mock_response


    def test_create_response_with_all_params_openai(self):
        """
        Prueba el enrutamiento a OpenAI con todos los parámetros opcionales.
        """
        model = "gpt-4o"
        input_data = [{"role": "user", "content": "Hola"}]
        tools_data = [{"type": "function", "function": {"name": "get_weather"}}]
        self.util_mock.is_openai_model.return_value = True

        self.proxy.create_response(
            model=model,
            input=input_data,
            previous_response_id="prev-123",
            tools=tools_data,
            text={"some": "text"},
            reasoning={"some": "reasoning"},
            tool_choice="specific_tool"
        )

        self.mock_openai_adapter_instance.create_response.assert_called_once_with(
            model=model,
            input=input_data,
            previous_response_id="prev-123",
            tools=tools_data,
            text={"some": "text"},
            reasoning={"some": "reasoning"},
            tool_choice="specific_tool"
        )
        self.mock_gemini_adapter_instance.create_response.assert_not_called()

    def test_create_response_raises_for_unsupported_model(self):
        """
        Prueba que create_response lanza una IAToolkitException para un modelo no soportado.
        """
        self.util_mock.is_openai_model.return_value = False
        self.util_mock.is_gemini_model.return_value = False
        with pytest.raises(IAToolkitException) as excinfo:
            self.proxy.create_response(model="unsupported-model", input=[])

        assert excinfo.value.error_type == IAToolkitException.ErrorType.LLM_ERROR
        assert "Modelo no soportado: unsupported-model" in str(excinfo.value)

