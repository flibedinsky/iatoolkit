import pytest
from flask import Flask
from unittest.mock import MagicMock
from iatoolkit.views.llmquery_web_view import LLMQueryWebView
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.auth_service import AuthService


class TestLLMQueryWebView:
    """Tests for the web-only query view."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.mock_auth = MagicMock(spec=AuthService)
        self.mock_query = MagicMock(spec=QueryService)

        view = LLMQueryWebView.as_view(
            'llm_query_web',
            auth_service=self.mock_auth,
            query_service=self.mock_query
        )
        self.app.add_url_rule('/<company_short_name>/llm_query', view_func=view, methods=['POST'])

    def test_web_query_success(self):
        """Tests a successful query from an authenticated web session user."""
        # Arrange
        self.mock_auth.verify.return_value = {"success": True, "user_identifier": "local-user-1"}
        self.mock_query.llm_query.return_value = {"answer": "Success from web"}

        # Act
        response = self.client.post('/test-co/llm_query', json={"question": "Hi"})

        # Assert
        assert response.status_code == 200
        assert response.json == {"answer": "Success from web"}
        self.mock_auth.verify.assert_called_once()
        self.mock_query.llm_query.assert_called_once()
        # Verify the unified identifier from the session is passed to the service
        assert self.mock_query.llm_query.call_args.kwargs['user_identifier'] == 'local-user-1'
        assert self.mock_query.llm_query.call_args.kwargs['question'] == 'Hi'

    def test_web_query_auth_failure(self):
        """Tests that the view returns a 401 if the web session is invalid."""
        # Arrange
        self.mock_auth.verify.return_value = {"success": False, "error_message": "No active session",
                                              "status_code": 401}

        # Act
        response = self.client.post('/test-co/llm_query', json={"question": "Hi"})

        # Assert
        assert response.status_code == 401
        assert "No active session" in response.json['error']
        self.mock_query.llm_query.assert_not_called()