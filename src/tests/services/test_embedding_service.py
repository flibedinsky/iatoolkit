# tests/services/test_embedding_service.py

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np
import base64
from iatoolkit.repositories.models import Company

# Import the classes to be tested, including the new wrappers
from iatoolkit.services.embedding_service import (
    EmbeddingClientFactory,
    EmbeddingService,
    HuggingFaceClientWrapper,
    OpenAIClientWrapper,
    EmbeddingClientWrapper
)
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.i18n_service import I18nService
from iatoolkit.repositories.profile_repo import ProfileRepo


class TestEmbeddingService:
    """
    Test suite for the EmbeddingService and its dependent EmbeddingClientFactory.
    """

    # --- Test Data ---
    MOCK_CONFIG_HF = {
        'provider': 'huggingface',
        'model': 'hf-model',
        'api_key_name': 'HF_KEY'
    }
    MOCK_CONFIG_OPENAI = {
        'provider': 'openai',
        'model': 'openai-model',
        'api_key_name': 'OPENAI_KEY'
    }
    SAMPLE_VECTOR = [0.1, 0.2, 0.3, 0.4]

    @pytest.fixture(autouse=True)
    def setup(self):
        """
        Set up a mock ConfigurationService and instantiate the factory and service for each test.
        """
        self.mock_config_service = Mock(spec=ConfigurationService)

        # Configure the mock to return different configs for different companies
        def get_config_side_effect(company_short_name, key):
            if key == 'embedding_provider':
                if company_short_name == 'company_hf':
                    return self.MOCK_CONFIG_HF
                if company_short_name == 'company_openai':
                    return self.MOCK_CONFIG_OPENAI
            return None

        self.mock_config_service.get_configuration.side_effect = get_config_side_effect

        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.mock_company = Company(id=1, short_name='acme')
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company

        self.mock_i18n_service = MagicMock(spec=I18nService)
        self.mock_i18n_service.t.side_effect = lambda key, **kwargs: f"translated:{key}"

        # Instantiate the classes under test
        self.client_factory = EmbeddingClientFactory(config_service=self.mock_config_service)
        self.embedding_service = EmbeddingService(client_factory=self.client_factory,
                                                  profile_repo=self.mock_profile_repo,
                                                 i18n_service=self.mock_i18n_service)

    # --- Factory Tests ---

    def test_factory_creates_huggingface_wrapper(self, mocker):
        """Tests that the factory correctly creates a HuggingFaceClientWrapper."""
        mocker.patch('os.getenv', return_value='fake-hf-key')
        mock_hf_client_class = mocker.patch('iatoolkit.services.embedding_service.InferenceClient')

        # Act
        wrapper = self.client_factory.get_client('company_hf')

        # Assert
        assert isinstance(wrapper, HuggingFaceClientWrapper)
        mock_hf_client_class.assert_called_once_with(model='hf-model', token='fake-hf-key')
        assert wrapper.model == 'hf-model'

    def test_factory_creates_openai_wrapper(self, mocker):
        """Tests that the factory correctly creates an OpenAIClientWrapper."""
        mocker.patch('os.getenv', return_value='fake-openai-key')
        mock_openai_client_class = mocker.patch('iatoolkit.services.embedding_service.OpenAI')

        # Act
        wrapper = self.client_factory.get_client('company_openai')

        # Assert
        assert isinstance(wrapper, OpenAIClientWrapper)
        mock_openai_client_class.assert_called_once_with(api_key='fake-openai-key')
        assert wrapper.model == 'openai-model'

    def test_factory_returns_cached_wrapper(self, mocker):
        """Tests that the factory caches the wrapper instance on subsequent calls."""
        mocker.patch('os.getenv', return_value='fake-key')
        mock_hf_client_class = mocker.patch('iatoolkit.services.embedding_service.InferenceClient')

        # Act
        wrapper1 = self.client_factory.get_client('company_hf')
        wrapper2 = self.client_factory.get_client('company_hf')

        # Assert
        mock_hf_client_class.assert_called_once()  # The underlying client should only be created once
        assert wrapper1 is wrapper2  # The returned wrapper must be the same object instance

    def test_factory_raises_error_if_api_key_is_not_set(self, mocker):
        """Tests that a ValueError is raised if the API key environment variable is missing."""
        mocker.patch('os.getenv', return_value=None)
        with pytest.raises(ValueError, match="Environment variable 'HF_KEY' is not set"):
            self.client_factory.get_client('company_hf')

    # --- Service Tests (Provider Agnostic) ---

    def test_service_embed_text_returns_vector(self, mocker):
        """
        Tests that embed_text correctly calls the wrapper's interface and returns a vector.
        This test is provider-agnostic.
        """
        # Arrange
        mock_wrapper = MagicMock(spec=EmbeddingClientWrapper)
        mock_wrapper.get_embedding.return_value = self.SAMPLE_VECTOR
        mocker.patch.object(self.client_factory, 'get_client', return_value=mock_wrapper)

        # Act
        # FIX: Correct argument order: text, then company_short_name
        result = self.embedding_service.embed_text("any_company", "some text", )

        # Assert
        self.client_factory.get_client.assert_called_once_with("any_company")
        mock_wrapper.get_embedding.assert_called_once_with("some text")
        assert result == self.SAMPLE_VECTOR

    def test_service_embed_text_returns_base64(self, mocker):
        """
        Tests that embed_text correctly returns a base64 string when requested.
        This test is provider-agnostic.
        """
        # Arrange
        mock_wrapper = MagicMock(spec=EmbeddingClientWrapper)
        mock_wrapper.get_embedding.return_value = self.SAMPLE_VECTOR
        mocker.patch.object(self.client_factory, 'get_client', return_value=mock_wrapper)

        # Act
        # FIX: Correct argument order
        result = self.embedding_service.embed_text("any_company", "some text", to_base64=True)

        # Assert
        expected_base64 = base64.b64encode(np.array(self.SAMPLE_VECTOR, dtype=np.float32).tobytes()).decode('utf-8')
        assert result == expected_base64
        mock_wrapper.get_embedding.assert_called_once_with("some text")

    def test_service_get_model_name(self, mocker):
        """
        Tests that get_model_name returns the model name from the wrapper.
        This test is provider-agnostic.
        """
        # Arrange
        mock_wrapper = MagicMock(spec=EmbeddingClientWrapper)
        mock_wrapper.model = "the-correct-model"
        mocker.patch.object(self.client_factory, 'get_client', return_value=mock_wrapper)

        # Act
        model_name = self.embedding_service.get_model_name("any_company")

        # Assert
        self.client_factory.get_client.assert_called_once_with("any_company")
        assert model_name == "the-correct-model"