# tests/views/test_external_login_view.py
import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.views.external_login_view import ExternalLoginView, RedeemTokenApiView
from iatoolkit.views.base_login_view import BaseLoginView

# --- Tests for ExternalLoginView ---

class TestExternalLoginView:
    @pytest.fixture(autouse=True)
    def setup_method(self, monkeypatch):
        self.app = Flask(__name__)
        self.client = self.app.test_client()

        # Mocks for all services used by BaseLoginView and its children
        self.auth_service = MagicMock()
        self.profile_service = MagicMock()
        self.jwt_service = MagicMock()
        self.branding_service = MagicMock()
        self.onboarding_service = MagicMock()
        self.query_service = MagicMock()
        self.prompt_service = MagicMock()

        # A single, comprehensive patch for BaseLoginView's constructor
        def patched_base_init(instance, **kwargs):
            # This will be used by any view inheriting from BaseLoginView
            instance.auth_service = self.auth_service
            instance.profile_service = self.profile_service
            instance.jwt_service = self.jwt_service
            instance.branding_service = self.branding_service
            instance.onboarding_service = self.onboarding_service
            instance.query_service = self.query_service
            instance.prompt_service = self.prompt_service

        monkeypatch.setattr(BaseLoginView, "__init__", patched_base_init)

        # Register the view under test
        self.app.add_url_rule(
            "/<company_short_name>/external_login",
            view_func=ExternalLoginView.as_view("external_login"),
            methods=["POST"],
        )

        self.company_short_name = "acme"
        self.user_identifier = "ext-123"

        # Default success cases for mocks
        self.profile_service.get_company_by_short_name.return_value = MagicMock()
        self.auth_service.verify.return_value = {"success": True}

    def test_missing_body_or_key_returns_400(self):
        """Tests that a request with an empty JSON body or missing key returns 400."""
        # Test with an empty but valid JSON object
        resp_empty = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={}
        )
        assert resp_empty.status_code == 400

        # Test with a JSON object that's missing the required 'user_identifier' key
        resp_missing_key = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"other_data": "value"}
        )
        assert resp_missing_key.status_code == 400

    def test_company_not_found_returns_404(self):
        self.profile_service.get_company_by_short_name.return_value = None
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"user_identifier": self.user_identifier},
        )
        assert resp.status_code == 404

    def test_empty_external_user_id_returns_404(self):
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"user_identifier": ""},
        )
        assert resp.status_code == 404

    def test_auth_failure_returns_401(self):
        self.auth_service.verify.return_value = {"success": False, "error": "denied"}
        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"user_identifier": self.user_identifier},
        )
        assert resp.status_code == 401
        self.auth_service.verify.assert_called_once()
        assert "denied" in resp.get_json().get("error")

    def test_success_delegates_to_base_handler(self, monkeypatch):
        def fake_handle(_self, csn, uid, company):
            return "OK", 200
        monkeypatch.setattr(BaseLoginView, "_handle_login_path", fake_handle, raising=True)

        resp = self.client.post(
            f"/{self.company_short_name}/external_login",
            json={"user_identifier": self.user_identifier},
        )
        assert resp.status_code == 200
        assert resp.data == b"OK"
        self.profile_service.create_external_user_session.assert_called_once()

    def test_handle_path_exception_returns_500_json(self):
        with patch.object(BaseLoginView, "_handle_login_path", side_effect=Exception("boom")):
            resp = self.client.post(
                f"/{self.company_short_name}/external_login",
                json={"user_identifier": self.user_identifier},
            )
        assert resp.status_code == 500
        assert resp.is_json
        assert "boom" in resp.get_json().get("error", "")


# --- Tests for RedeemTokenApiView (ahora separada para mayor claridad) ---
class TestRedeemTokenApiView:
    @pytest.fixture(autouse=True)
    def setup_method(self, monkeypatch):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.auth_service = MagicMock()

        # Usamos el mismo parcheador para BaseLoginView que en la clase anterior
        def patched_base_init(instance, **kwargs):
            instance.auth_service = self.auth_service
            # Añadimos otros mocks que BaseLoginView pueda necesitar para que no falle
            instance.profile_service = MagicMock()
            instance.jwt_service = MagicMock()

        monkeypatch.setattr(BaseLoginView, "__init__", patched_base_init)

        self.app.add_url_rule(
            "/<company_short_name>/api/redeem_token",
            view_func=RedeemTokenApiView.as_view("redeem_token"),
            methods=["POST"],
        )
        self.company_short_name = "acme"

    def test_redeem_missing_token_returns_400(self):
        resp = self.client.post(f"/{self.company_short_name}/api/redeem_token", json={})
        assert resp.status_code == 400
        assert "Falta token" in resp.get_json().get("error", "")

    def test_redeem_failure_returns_401(self):
        self.auth_service.redeem_token_for_session.return_value = {
            'success': False,
            'error': 'Token es inválido'
        }
        resp = self.client.post(
            f"/{self.company_short_name}/api/redeem_token", json={"token": "bad"}
        )
        assert resp.status_code == 401
        assert "Token es inválido" in resp.get_json().get("error", "")
        self.auth_service.redeem_token_for_session.assert_called_once_with(
            company_short_name=self.company_short_name, token="bad"
        )

    def test_redeem_success_returns_200(self):
        self.auth_service.redeem_token_for_session.return_value = {'success': True}
        resp = self.client.post(
            f"/{self.company_short_name}/api/redeem_token", json={"token": "good"}
        )
        assert resp.status_code == 200
        assert resp.get_json().get("status") == "ok"
        self.auth_service.redeem_token_for_session.assert_called_once_with(
            company_short_name=self.company_short_name, token="good"
        )