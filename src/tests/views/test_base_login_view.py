# tests/views/test_base_login_view.py
# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from iatoolkit.views.base_login_view import BaseLoginView

# Constants for test data
COMPANY_SHORT_NAME = "test-co"
USER_IDENTIFIER = "test-user@example.com"


class TestBaseLoginView:
    """Test suite for the BaseLoginView class."""

    def setup_method(self):
        """
        Set up a new view instance and fresh mocks before each test method runs.
        This ensures test isolation.
        """
        self.mock_services = {
            "profile_service": MagicMock(),
            "branding_service": MagicMock(),
            "onboarding_service": MagicMock(),
            "query_service": MagicMock(),
            "chat_page_render_service": MagicMock(),
        }
        self.view_instance = BaseLoginView(**self.mock_services)

    def test_handle_login_path_slow_path(self):
        """
        Tests the 'slow path' where a context rebuild is needed.
        It should render the onboarding_shell.html template.
        """
        # --- Arrange ---
        # Simulate that a rebuild is needed
        self.mock_services["query_service"].prepare_context.return_value = {'rebuild_needed': True}

        # Mock company object and service returns
        mock_company = MagicMock()
        self.mock_services["branding_service"].get_company_branding.return_value = {"logo": "logo.png"}
        self.mock_services["onboarding_service"].get_onboarding_cards.return_value = [{"title": "Card 1"}]

        # We need a Flask app context to use url_for and render_template
        app = Flask(__name__)
        app.add_url_rule(f'/<company_short_name>/chat', endpoint='chat')

        # --- Act ---
        with app.test_request_context():
            # Patch render_template to capture its call without executing it
            with patch('iatoolkit.views.base_login_view.render_template') as mock_render_template:
                self.view_instance._handle_login_path(COMPANY_SHORT_NAME, USER_IDENTIFIER, mock_company)

        # --- Assert ---
        # 1. Verify that prepare_context was called correctly.
        self.mock_services["query_service"].prepare_context.assert_called_once_with(
            company_short_name=COMPANY_SHORT_NAME,
            user_identifier=USER_IDENTIFIER
        )

        # 2. Verify that services for the slow path were called.
        self.mock_services["branding_service"].get_company_branding.assert_called_once_with(mock_company)
        self.mock_services["onboarding_service"].get_onboarding_cards.assert_called_once_with(mock_company)

        # 3. Verify that the fast path service was NOT called.
        self.mock_services["chat_page_render_service"].render_chat_page.assert_not_called()

        # 4. Verify that the correct template was rendered with the correct context.
        mock_render_template.assert_called_once()
        template_name = mock_render_template.call_args[0][0]
        context = mock_render_template.call_args[1]

        assert template_name == "onboarding_shell.html"
        assert "iframe_src_url" in context
        assert context["branding"] == {"logo": "logo.png"}
        assert context["onboarding_cards"] == [{"title": "Card 1"}]

    def test_handle_login_path_fast_path(self):
        """
        Tests the 'fast path' where the context is already cached.
        It should call the ChatPageRenderService to render the chat page.
        """
        # --- Arrange ---
        # Simulate that a rebuild is NOT needed
        self.mock_services["query_service"].prepare_context.return_value = {'rebuild_needed': False}

        # Mock company object and the expected return from the render service
        mock_company = MagicMock()
        expected_render_result = "<html>Chat Page</html>"
        self.mock_services["chat_page_render_service"].render_chat_page.return_value = expected_render_result

        # --- Act ---
        result = self.view_instance._handle_login_path(COMPANY_SHORT_NAME, USER_IDENTIFIER, mock_company)

        # --- Assert ---
        # 1. Verify that prepare_context was called correctly.
        self.mock_services["query_service"].prepare_context.assert_called_once_with(
            company_short_name=COMPANY_SHORT_NAME,
            user_identifier=USER_IDENTIFIER
        )

        # 2. Verify that the fast path service WAS called.
        self.mock_services["chat_page_render_service"].render_chat_page.assert_called_once_with(
            COMPANY_SHORT_NAME, mock_company
        )

        # 3. Verify that services for the slow path were NOT called.
        self.mock_services["branding_service"].get_company_branding.assert_not_called()
        self.mock_services["onboarding_service"].get_onboarding_cards.assert_not_called()

        # 4. Verify that the result is what the render service returned.
        assert result == expected_render_result
