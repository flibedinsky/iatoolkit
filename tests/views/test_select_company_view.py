# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from services.profile_service import ProfileService
from repositories.llm_query_repo import LLMQueryRepo
from repositories.profile_repo import ProfileRepo
from views.select_company_view import SelectCompanyView
from repositories.models import Company, Function, User
from datetime import datetime, timezone
from common.session_manager import SessionManager
from common.auth import IAuthentication


class TestSelectCompanyView:
    @staticmethod
    def create_app():
        app = Flask(__name__)
        app.secret_key = 'test_secret_key'
        app.testing = True

        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y los mocks antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()

        # Mock para los servicios necesarios
        self.profile_service = MagicMock(spec=ProfileService)
        self.query_repo = MagicMock(spec=LLMQueryRepo)
        self.profile_repo = MagicMock(spec=ProfileRepo)
        self.iauthentication = MagicMock(spec=IAuthentication)
        self.iauthentication.verify.return_value = {
            'success': True,
            'company_id': 101,
            'external_user_id': 'test_user_id'
        }

        self.company = Company(id=1, name='iatoolkit', logo_file='iatoolkit.jpg')
        self.profile_service.get_companies.return_value = [self.company]

        self.query_repo.get_company_functions.return_value = [Function(company_id=1, name="func1",  description='function number 1')]
        self.profile_repo.get_company_by_id.return_value = self.company
        self.user = User(email="test@email.com", super_user=True)
        self.user.companies = [Company(id=2, name="Test Company 2")]

        # Registrar la vista
        view = SelectCompanyView.as_view("select_company",
                                         profile_service=self.profile_service,
                                         query_repo=self.query_repo,
                                         profile_repo=self.profile_repo,
                                         iauthentication=self.iauthentication)
        self.app.add_url_rule("/<company_short_name>/select_company", view_func=view, methods=["GET", "POST"])

        # Mock values
        mock_values = {
            'user': {'id': 1, 'username': 'test_user'},
            'user_id': 1,
            'company_id': 100,
            'company_short_name': 'test_company',
            'last_activity': datetime.now(timezone.utc).timestamp()
        }

        # Mockear SessionManager.get
        mock_session_manager = MagicMock(spec=SessionManager)  # <- Mock de la clase
        mock_session_manager.get.side_effect = lambda key, default=None: mock_values.get(key, default)

        with patch('views.select_company_view.SessionManager', new=mock_session_manager), \
                patch('common.auth.SessionManager', new=mock_session_manager):  # <-  Aplicar el mock
            with self.app.test_request_context():  # Necesario para Flask
                yield

    def test_get_when_no_auth(self):
        self.iauthentication.verify.return_value = {'error_message': 'error in authentication'}
        response = self.client.get("/test_company/select_company")

        assert response.status_code == 401

    @patch("views.select_company_view.render_template")
    def test_get_when_invalid_company(self, mock_render_template):
        self.profile_service.get_company_by_short_name.return_value = None
        mock_render_template.return_value = "<html><body><h1>Select Company</h1></body></html>"
        response = self.client.get("/test_company/select_company")

        assert response.status_code == 404

    @patch("views.select_company_view.render_template")
    def test_get_when_ok(self, mock_render_template):
        mock_render_template.return_value = "<html><body><h1>Select Company</h1></body></html>"
        response = self.client.get("/test_company/select_company")

        assert response.status_code == 200

    def test_post_when_no_auth(self):
        self.iauthentication.verify.return_value = {'error_message': 'error in authentication'}
        response = self.client.post("/test_company/select_company", data={"company_id": 2})

        assert response.status_code == 401

    @patch("views.select_company_view.render_template")
    def test_post_when_invalid_company(self, mock_render_template):
        self.profile_service.get_company_by_short_name.return_value = None
        mock_render_template.return_value = "<html><body><h1>Select Company</h1></body></html>"
        response = self.client.post("/test_company/select_company", data={"company_id": 2})

        assert response.status_code == 404

    @patch("views.select_company_view.render_template")
    def test_post_when_exception(self, mock_render_template):
        self.profile_service.set_user_session.side_effect = Exception("Unexpected error")

        response = self.client.post("/test_company/select_company", data={"company_id": 2})
        assert response.status_code == 500

    @patch("views.select_company_view.render_template")
    @patch("views.select_company_view.redirect")
    def test_post_when_success(self, mock_redirect, mock_render_template):
        mock_redirect.return_value = "redirect_to_url"
        self.profile_service.update_user.return_value = self.user

        response = self.client.post("/test_company/select_company", data={"company_id": 2})
        self.profile_service.set_user_session.assert_called_once()

