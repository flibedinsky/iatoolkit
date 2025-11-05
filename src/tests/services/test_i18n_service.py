# tests/services/test_i18n_service.py
import pytest
from unittest.mock import Mock, patch
from iatoolkit.services.i18n_service import I18nService
from iatoolkit.common.util import Utility
from iatoolkit.services.language_service import LanguageService # <-- 1. Importar

class TestI18nService:
    """
    Unit tests for the I18nService.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """
        Pytest fixture that runs before each test.
        - Mocks Utility and LanguageService dependencies.
        - Patches _load_translations to prevent file I/O.
        - Creates a fresh instance of I18nService.
        - Provides a mock translations dictionary for testing.
        """
        self.mock_util = Mock(spec=Utility)
        self.mock_language_service = Mock(spec=LanguageService) # <-- 2. Crear mock

        # Prevent the real __init__ from reading files by patching the loader
        with patch.object(I18nService, '_load_translations', return_value=None):
            self.i18n_service = I18nService(
                util=self.mock_util,
                language_service=self.mock_language_service # <-- 3. Inyectar mock
            )

        # Manually inject translations for a controlled test environment
        self.mock_translations = {
            'es': {
                'ui': {'login_button': 'Acceder'},
                'errors': {'general': {'unexpected_error': 'Ha ocurrido un error inesperado.'}},
                'messages': {'welcome': 'Bienvenido, {name}!'}
            },
            'en': {
                'ui': {'login_button': 'Login'},
                'messages': {'welcome': 'Welcome, {name}!'}
            }
        }
        self.i18n_service.translations = self.mock_translations

    def test_t_uses_language_service_when_no_lang_provided(self):
        """
        Tests the primary use case: t() calls LanguageService to get the current language.
        """
        # Arrange
        self.mock_language_service.get_current_language.return_value = 'en'

        # Act
        translation = self.i18n_service.t('ui.login_button')

        # Assert
        assert translation == 'Login'
        self.mock_language_service.get_current_language.assert_called_once()

    def test_t_uses_explicit_lang_when_provided(self):
        """
        Tests that if 'lang' is passed explicitly, it overrides the LanguageService.
        """
        # Arrange
        self.mock_language_service.get_current_language.return_value = 'es' # Automatic is 'es'

        # Act
        translation = self.i18n_service.t('ui.login_button', lang='en') # But we explicitly ask for 'en'

        # Assert
        assert translation == 'Login'
        # CRUCIAL: Verify that LanguageService was NOT called
        self.mock_language_service.get_current_language.assert_not_called()

    def test_t_uses_fallback_with_automatic_language(self):
        """
        Tests that fallback logic works correctly when using automatic language detection.
        """
        # Arrange
        self.mock_language_service.get_current_language.return_value = 'en'

        # Act
        translation = self.i18n_service.t('errors.general.unexpected_error')

        # Assert
        assert translation == 'Ha ocurrido un error inesperado.'
        self.mock_language_service.get_current_language.assert_called_once()

    def test_t_not_found_returns_key_with_automatic_language(self):
        """
        Tests that the key is returned if not found, even with automatic language.
        """
        # Arrange
        self.mock_language_service.get_current_language.return_value = 'en'

        # Act
        translation = self.i18n_service.t('non.existent.key')

        # Assert
        assert translation == 'non.existent.key'

    def test_t_with_arguments_and_automatic_language(self):
        """
        Tests variable formatting with automatic language detection.
        """
        # Arrange
        self.mock_language_service.get_current_language.return_value = 'en'

        # Act
        translation = self.i18n_service.t('messages.welcome', name='Tester')

        # Assert
        assert translation == 'Welcome, Tester!'

