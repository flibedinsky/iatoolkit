# tests/services/test_language_service.py
import pytest
from flask import Flask, g
from unittest.mock import MagicMock, patch
from iatoolkit.services.language_service import LanguageService
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Company, User


class TestLanguageService:
    """
    Unit tests for the LanguageService.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """
        Pytest fixture that runs before each test.
        - Mocks the ProfileRepo dependency.
        - Creates a fresh instance of LanguageService.
        - Creates a Flask app to provide a request context for tests.
        """
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.language_service = LanguageService(profile_repo=self.mock_profile_repo)

        # A Flask app is necessary to create a request context
        self.app = Flask(__name__)

        # Mock company objects for predictable test data
        self.company_en = Company(id=1, short_name='acme-en', default_language='en')
        self.company_fr = Company(id=2, short_name='acme-fr', default_language='fr')
        self.company_no_lang = Company(id=3, short_name='acme-no-lang', default_language=None)

        # Mock user objects
        self.user_with_lang_de = User(id=1, email='user-de@acme.com', preferred_language='de')
        self.user_without_lang = User(id=2, email='user-no-lang@acme.com', preferred_language=None)

        # Register a dummy route that matches the URL structure used in tests.
        # This allows Flask's test context to correctly parse `company_short_name`.
        @self.app.route('/<company_short_name>/login')
        def dummy_route_for_test(company_short_name):
            return "ok"

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_priority_1_user_preference_overrides_all(self, mock_session_manager):
        """
        Tests that if a logged-in user has a preferred language, it is used,
        ignoring the company's default language.
        """
        # Arrange
        # Session has both user and company. Company lang is 'en'.
        mock_session_manager.get.side_effect = lambda key: 'user-de@acme.com' if key == 'user_identifier' else 'acme-en'
        # Repo returns a user whose preferred language is 'de'
        self.mock_profile_repo.get_user_by_email.return_value = self.user_with_lang_de
        # Repo also returns the company object, though it should be ignored.
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_en

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'de' # The user's preference ('de') should win.
            self.mock_profile_repo.get_user_by_email.assert_called_once_with('user-de@acme.com')
            # Verify that it didn't even need to check the company's language
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()
    @patch('iatoolkit.services.language_service.SessionManager')
    def test_priority_2_company_language_if_user_has_no_preference(self, mock_session_manager):
        """
        Tests that if a user is logged in but has no preferred language,
        the company's default language is used.
        """
        # Arrange
        # Session has user and company. Company lang is 'en'.
        mock_session_manager.get.side_effect = lambda key: 'user-no-lang@acme.com' if key == 'user_identifier' else 'acme-en'
        # Repo returns a user WITHOUT a preferred language
        self.mock_profile_repo.get_user_by_email.return_value = self.user_without_lang
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_en

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'en' # The company's language ('en') should be used.
            self.mock_profile_repo.get_user_by_email.assert_called_once_with('user-no-lang@acme.com')
            # It should have proceeded to check the company language
            self.mock_profile_repo.get_company_by_short_name.assert_called_once_with('acme-en')

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_get_language_from_url_args(self, mock_session_manager):
        """
        Test that if no session is found, the language is determined from the URL argument.
        """
        # Arrange
        mock_session_manager.get.return_value = None  # No active session for both company and user
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_fr

        # Create a request context that simulates a URL like /acme-fr/login
        with self.app.test_request_context('/acme-fr/login'):
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'fr'

            # --- INICIO DE LA SOLUCIÓN ---
            # Verify the calls to SessionManager.
            # It's called twice: once for company_short_name, once for user_identifier.
            from unittest.mock import call
            expected_calls = [call('company_short_name'), call('user_identifier')]
            mock_session_manager.get.assert_has_calls(expected_calls, any_order=True)
            assert mock_session_manager.get.call_count == 2
    @patch('iatoolkit.services.language_service.SessionManager')
    def test_fallback_language_if_company_has_no_lang(self, mock_session_manager):
        """
        Test that it returns the fallback language ('es') if the company has no default_language set.
        """
        # --- INICIO DE LA SOLUCIÓN ---
        # Arrange
        # Configure a side effect to return different values based on the argument
        def session_get_side_effect(key):
            if key == 'company_short_name':
                return 'acme-no-lang'
            if key == 'user_identifier':
                return None  # Explicitly simulate no logged-in user
            return None
        mock_session_manager.get.side_effect = session_get_side_effect
        # --- FIN DE LA SOLUCIÓN ---

        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_no_lang

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'es'


    @patch('iatoolkit.services.language_service.SessionManager')
    def test_fallback_language_if_no_context_found(self, mock_session_manager):
        """
        Test that it returns the fallback language ('es') if no company context can be found at all.
        """
        # Arrange
        mock_session_manager.get.return_value = None # No session

        # Simulate a request to a URL without a company_short_name, e.g., a health check endpoint
        with self.app.test_request_context('/health'):
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'es'
            # Ensure it didn't even try to query the database
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()

    def test_caching_in_g_object(self):
        """
        Test that the language is cached in g.lang to avoid re-computation within the same request.
        """
        with self.app.test_request_context():
            # Arrange: Manually set the language in the 'g' object before calling the service
            g.lang = 'de'

            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'de'
            # CRUCIAL: Verify that no external calls were made because the value was cached.
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()