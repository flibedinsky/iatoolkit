# tests/services/test_chat_page_render_service.py
# IAToolkit is open source software.

import pytest
from unittest.mock import MagicMock, patch
from iatoolkit.services.chat_page_render_service import ChatPageRenderService


class TestChatPageRenderService:
    """Test suite for ChatPageRenderService."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Centralized setup: create service with mocked dependencies."""
        self.profile_service = MagicMock()
        self.prompt_service = MagicMock()
        self.branding_service = MagicMock()

        self.service = ChatPageRenderService(
            profile_service=self.profile_service,
            prompt_service=self.prompt_service,
            branding_service=self.branding_service,
        )

        # Common inputs
        self.company_short_name = "acme"
        self.company_obj = MagicMock()

        # Default mocks behavior
        self.profile_service.get_current_session_info.return_value = {
            "user_identifier": 'user_ident',
            "company_short_name": 'company',
            "profile": {
                "user_is_local": True,
                "user_email": "user@example.com",
            }
        }
        self.prompt_service.get_user_prompts.return_value = [{"id": "p1"}]
        self.branding_service.get_company_branding.return_value = {"logo": "x.png"}

    def test_render_chat_page_calls_dependencies_and_renders(self):
        """Should gather session, prompts, branding and render chat.html."""
        with patch("iatoolkit.services.chat_page_render_service.render_template") as mock_rt:
            mock_rt.return_value = "<html>chat</html>"

            result = self.service.render_chat_page(self.company_short_name, self.company_obj)

        # Assert render result is returned
        assert result == "<html>chat</html>"

        # Assert dependencies are called with expected arguments
        self.profile_service.get_current_session_info.assert_called_once()
        self.prompt_service.get_user_prompts.assert_called_once_with(self.company_short_name)
        self.branding_service.get_company_branding.assert_called_once_with(self.company_obj)

        # Assert template and context
        mock_rt.assert_called_once()
        template_name = mock_rt.call_args[0][0]
        context = mock_rt.call_args[1]
        assert template_name == "chat.html"
        assert context["user_is_local"] is True
        assert context["user_email"] == "user@example.com"
        assert context["branding"] == {"logo": "x.png"}
        assert context["prompts"] == [{"id": "p1"}]
        # iatoolkit_base_url can be None in tests; just ensure key exists
        assert "iatoolkit_base_url" in context

    def test_render_chat_page_handles_missing_profile_fields(self):
        """Should not fail if profile data is missing; defaults to None."""
        self.profile_service.get_current_session_info.return_value = {"profile": {}}

        with patch("iatoolkit.services.chat_page_render_service.render_template") as mock_rt:
            mock_rt.return_value = "<html>chat</html>"

            _ = self.service.render_chat_page(self.company_short_name, self.company_obj)

        context = mock_rt.call_args[1]
        assert context["user_is_local"] is None
        assert context["user_email"] is None

    def test_render_chat_page_handles_missing_profile_key(self):
        """Should not fail if 'profile' key is missing."""
        self.profile_service.get_current_session_info.return_value = {}

        with patch("iatoolkit.services.chat_page_render_service.render_template") as mock_rt:
            mock_rt.return_value = "<html>chat</html>"
            _ = self.service.render_chat_page(self.company_short_name, self.company_obj)

        context = mock_rt.call_args[1]
        assert context["user_is_local"] is None
        assert context["user_email"] is None

    def test_render_chat_page_propagates_dependency_errors(self):
        """If a dependency raises, the exception should bubble up (no swallow)."""
        self.prompt_service.get_user_prompts.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            self.service.render_chat_page(self.company_short_name, self.company_obj)