import pytest
from unittest.mock import MagicMock, patch
from iatoolkit.services.auth_service import AuthService
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.jwt_service import JWTService
from iatoolkit.repositories.database_manager import DatabaseManager
from iatoolkit.repositories.models import ApiKey, Company
from flask import Flask


class TestAuthServiceVerify:
    """
    Tests for the verify() method, which checks for existing sessions or API keys.
    These tests DO NOT cover the login/redeem flows.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up mocks for verify() tests."""
        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_jwt_service = MagicMock(spec=JWTService)
        self.mock_db_manager = MagicMock(spec=DatabaseManager)

        # AuthService now requires all three dependencies
        self.service = AuthService(
            profile_service=self.mock_profile_service,
            jwt_service=self.mock_jwt_service,
            db_manager=self.mock_db_manager
        )
        self.app = Flask(__name__)
        self.app.testing = True

    def test_verify_success_with_flask_session(self):
        """verify() should succeed if a valid Flask session is found."""
        session_info = {"user_identifier": "123", "company_short_name": "testco"}
        self.mock_profile_service.get_current_session_info.return_value = session_info

        with self.app.test_request_context():
            result = self.service.verify()

        assert result['success'] is True
        assert result['user_identifier'] == "123"
        self.mock_profile_service.get_active_api_key_entry.assert_not_called()

    def test_verify_success_with_api_key(self):
        """verify() should succeed if a valid API key is provided."""
        self.mock_profile_service.get_current_session_info.return_value = {}
        mock_company = Company(id=1, short_name="apico")
        mock_api_key_entry = ApiKey(key="valid-api-key", company=mock_company)
        self.mock_profile_service.get_active_api_key_entry.return_value = mock_api_key_entry

        with self.app.test_request_context(headers={'Authorization': 'Bearer valid-api-key'}):
            result = self.service.verify()

        assert result['success'] is True
        assert result['company_short_name'] == "apico"
        self.mock_profile_service.get_active_api_key_entry.assert_called_once_with("valid-api-key")

    def test_verify_fails_with_invalid_api_key(self):
        """verify() should fail if the API key is invalid."""
        self.mock_profile_service.get_current_session_info.return_value = {}
        self.mock_profile_service.get_active_api_key_entry.return_value = None

        with self.app.test_request_context(headers={'Authorization': 'Bearer invalid-key'}):
            result = self.service.verify()

        assert result['success'] is False
        assert result['status_code'] == 401

    def test_verify_fails_with_no_credentials(self):
        """verify() should fail if no credentials are provided."""
        self.mock_profile_service.get_current_session_info.return_value = {}

        with self.app.test_request_context():
            result = self.service.verify()

        assert result['success'] is False
        assert result['status_code'] == 402


class TestAuthServiceLoginFlows:
    """
    Tests for the new login/redeem methods in AuthService and their logging side-effects.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self, monkeypatch):
        """Set up a mocked environment and patch the log_access method."""
        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_jwt_service = MagicMock(spec=JWTService)
        self.mock_db_manager = MagicMock(spec=DatabaseManager)

        self.service = AuthService(
            profile_service=self.mock_profile_service,
            jwt_service=self.mock_jwt_service,
            db_manager=self.mock_db_manager
        )
        self.app = Flask(__name__)
        self.app.testing = True

        # Mock the log_access method to prevent DB writes and to check its calls
        self.mock_log_access = MagicMock()
        monkeypatch.setattr(self.service, 'log_access', self.mock_log_access)

        # Common test data
        self.company_short_name = "acme"
        self.user_identifier = "user-123"
        self.email = "test@user.com"

    def test_login_local_user_success(self):
        """login_local_user should return success and log a successful 'local' access."""
        self.mock_profile_service.login.return_value = {'success': True, 'user_identifier': self.user_identifier}

        with self.app.test_request_context():
            result = self.service.login_local_user(self.company_short_name, self.email, "password")

        assert result['success'] is True
        self.mock_log_access.assert_called_once_with(
            company_short_name=self.company_short_name,
            auth_type='local',
            outcome='success',
            user_identifier=self.user_identifier
        )

    def test_login_local_user_failure(self):
        """login_local_user should return failure and log a failed 'local' access."""
        self.mock_profile_service.login.return_value = {'success': False, 'message': 'Wrong password'}

        with self.app.test_request_context():
            result = self.service.login_local_user(self.company_short_name, self.email, "wrong")

        assert result['success'] is False
        self.mock_log_access.assert_called_once_with(
            company_short_name=self.company_short_name,
            auth_type='local',
            outcome='failure',
            reason_code='INVALID_CREDENTIALS',
            user_identifier=self.email
        )

    def test_redeem_token_success(self):
        """redeem_token should succeed, create a session, and log a successful 'redeem_token' access."""
        self.mock_jwt_service.validate_chat_jwt.return_value = {'user_identifier': self.user_identifier}

        with self.app.test_request_context():
            result = self.service.redeem_token_for_session(self.company_short_name, "valid-token")

        assert result['success'] is True
        assert result['user_identifier'] == self.user_identifier
        self.mock_profile_service.set_session_for_user.assert_called_once_with(self.company_short_name, self.user_identifier)
        self.mock_log_access.assert_called_once_with(
            company_short_name=self.company_short_name,
            auth_type='redeem_token',
            outcome='success',
            user_identifier=self.user_identifier
        )

    def test_redeem_token_invalid_jwt(self):
        """redeem_token should fail for an invalid JWT and log a failed 'redeem_token' access."""
        self.mock_jwt_service.validate_chat_jwt.return_value = None

        with self.app.test_request_context():
            result = self.service.redeem_token_for_session(self.company_short_name, "invalid-token")

        assert result['success'] is False
        self.mock_profile_service.set_session_for_user.assert_not_called()
        self.mock_log_access.assert_called_once_with(
            company_short_name=self.company_short_name,
            auth_type='redeem_token',
            outcome='failure',
            reason_code='JWT_INVALID'
        )

    def test_redeem_token_session_creation_fails(self):
        """redeem_token should log a failure if session creation throws an exception."""
        self.mock_jwt_service.validate_chat_jwt.return_value = {'user_identifier': self.user_identifier}
        self.mock_profile_service.set_session_for_user.side_effect = Exception("DB connection error")

        with self.app.test_request_context():
            result = self.service.redeem_token_for_session(self.company_short_name, "valid-token")

        assert result['success'] is False
        self.mock_log_access.assert_called_once_with(
            company_short_name=self.company_short_name,
            auth_type='redeem_token',
            outcome='failure',
            reason_code='SESSION_CREATION_FAILED',
            user_identifier=self.user_identifier
        )