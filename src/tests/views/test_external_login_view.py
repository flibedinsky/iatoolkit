# tests/views/test_external_login_view.py
# IAToolkit is open source software.

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.views.base_login_view import BaseLoginView
from iatoolkit.views.external_login_view import ExternalLoginView


class TestExternalLoginView:
    """Test suite for ExternalLoginView."""

    @pytest.fixture(autouse=True)
    def setup_method(self, monkeypatch):
        """Centralized setup: app, client, and service mocks."""
        # Flask app and client
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.client = self.app.test_client()

        # Service mocks
        self.auth_service = MagicMock()                  # AuthService
        self.profile_service = MagicMock()
        self.query_service = MagicMock()
        self.chat_render_service = MagicMock()
        self.branding_service = MagicMock()
        self.onboarding_service = MagicMock()

        # Patch ExternalLoginView.__init__ to inject mocks before as_view is called
        original_init = ExternalLoginView.__init__

        def patched_init(instance, *args, **kwargs):
            """Call original __init__ with mocked services."""
            return original_init(
                instance,
                iauthentication=self.auth_service,
                profile_service=self.profile_service,
                branding_service=self.branding_service,
                onboarding_service=self.onboarding_service,
                query_service=self.query_service,
                chat_page_render_service=self.chat_render_service,
            )

        monkeypatch.setattr(ExternalLoginView, "__init__", patched_init)

        # Register endpoint after patching constructor
        self.app.add_url_rule(
            "/<company_short_name>/external_login",
            view_func=ExternalLoginView.as_view("external_login"),
            methods=["POST"],
        )

        # Common test values
        self.company_short_name = "acme"
        self.external_user_id = "ext-123"

        # Default: company exists
        self.profile_service.get_company_by_short_name.return_value = MagicMock()

    def test_missing_body_returns_400(self):
        """If content-type is JSON but body is empty/invalid, return 400."""
        # Case 1: Empty JSON body (Content-Type application/json)
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            data="",  # empty body
            content_type="application/json",
        )
        assert resp.status_code == 400

        # Case 2: JSON object without external_user_id
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"foo": "bar"},
        )
        assert resp.status_code == 400

    def test_company_not_found_returns_404(self):
        """If company does not exist, return 404."""
        self.profile_service.get_company_by_short_name.return_value = None

        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"external_user_id": self.external_user_id},
        )
        assert resp.status_code == 404

    def test_empty_external_user_id_returns_404(self):
        """If external_user_id is empty, return 404."""
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"external_user_id": ""},
        )
        assert resp.status_code == 404

    def test_auth_failure_returns_401(self):
        """If AuthService.verify fails, return 401."""
        self.auth_service.verify.return_value = {"success": False, "error": "denied"}

        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"external_user_id": self.external_user_id},
        )
        assert resp.status_code == 401
        self.auth_service.verify.assert_called_once()

    def test_success_delegates_to_base_handler(self, monkeypatch):
        """On success, it should create session and delegate to BaseLoginView._handle_login_path."""
        self.auth_service.verify.return_value = {"success": True}

        def fake_handle(instance, csn, uid, company):
            return "OK", 200

        monkeypatch.setattr(BaseLoginView, "_handle_login_path", fake_handle, raising=True)

        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"external_user_id": self.external_user_id},
        )

        assert resp.status_code == 200
        assert resp.data == b"OK"
        self.profile_service.create_external_user_session.assert_called_once()

    def test_handle_path_exception_returns_500(self):
        """If path handling raises, it should return 500 with JSON error."""
        self.auth_service.verify.return_value = {"success": True}
        with patch.object(BaseLoginView, "_handle_login_path", side_effect=Exception("boom")):
            resp = self.client.post(
                f"/{self.company_short_name}/external_login",
                json={"external_user_id": self.external_user_id},
            )

        assert resp.status_code == 500
        assert resp.is_json
        assert "error" in resp.get_json()