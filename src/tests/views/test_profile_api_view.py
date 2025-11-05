# tests/views/test_profile_api_view.py
import pytest
from flask import Flask
from unittest.mock import MagicMock
from iatoolkit.views.profile_api_view import UserLanguageApiView
from iatoolkit.services.auth_service import AuthService
from iatoolkit.services.profile_service import ProfileService

# --- Test Constants ---
MOCK_USER_IDENTIFIER = "user-123@example.com"
API_URL = "/api/profile/language"


class TestUserLanguageApiView:
    """
    Test suite for the UserLanguageApiView endpoint.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up a clean test environment before each test."""
        self.app = Flask(__name__)
        self.app.testing = True
        self.client = self.app.test_client()

        # Mocks for the injected services
        self.mock_auth_service = MagicMock(spec=AuthService)
        self.mock_profile_service = MagicMock(spec=ProfileService)

        # Register the view with the mocked dependencies
        view_func = UserLanguageApiView.as_view(
            'user_language_api',
            auth_service=self.mock_auth_service,
            profile_service=self.mock_profile_service
        )
        self.app.add_url_rule(API_URL, view_func=view_func, methods=['POST'])

        # By default, assume authentication is successful for most tests
        self.mock_auth_service.verify.return_value = {
            "success": True,
            'user_identifier': MOCK_USER_IDENTIFIER
        }

    def test_update_language_success(self):
        """
        Tests the happy path: user is authenticated, provides valid data,
        and the language is updated successfully.
        """
        # Arrange: Simulate a successful response from the profile service.
        self.mock_profile_service.update_user_language.return_value = {'success': True}

        # Act
        response = self.client.post(API_URL, json={'language': 'en'})

        # Assert
        assert response.status_code == 200
        assert response.json == {"message": "Language preference updated successfully"}

        # Verify that the auth and profile services were called correctly.
        self.mock_auth_service.verify.assert_called_once()
        self.mock_profile_service.update_user_language.assert_called_once_with(
            MOCK_USER_IDENTIFIER, 'en'
        )

    def test_update_language_when_auth_fails(self):
        """
        Tests that a 401 Unauthorized error is returned if the user is not authenticated.
        """
        # Arrange
        self.mock_auth_service.verify.return_value = {
            "success": False,
            "error_message": "Authentication required",
            "status_code": 401
        }

        # Act
        response = self.client.post(API_URL, json={'language': 'en'})

        # Assert
        assert response.status_code == 401
        assert "Authentication required" in response.json['error_message']
        self.mock_profile_service.update_user_language.assert_not_called()

    def test_update_language_handles_service_error(self):
        """
        Tests that a 400 error is returned if the profile service fails the update
        (e.g., unsupported language).
        """
        # Arrange
        self.mock_profile_service.update_user_language.return_value = {
            'success': False,
            'error': 'The selected language is not supported.'
        }

        # Act
        response = self.client.post(API_URL, json={'language': 'xx'})

        # Assert
        assert response.status_code == 400
        assert response.json['error'] == 'The selected language is not supported.'
        self.mock_profile_service.update_user_language.assert_called_once_with(
            MOCK_USER_IDENTIFIER, 'xx'
        )