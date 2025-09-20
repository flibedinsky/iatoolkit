# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from flask import Flask, jsonify
from unittest.mock import MagicMock, patch
from services.profile_service import ProfileService
from views.login_view import LoginView
from repositories.models import Company


class TestLoginView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.testing = True

        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y el mock antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.profile_service = MagicMock(spec=ProfileService)
        self.test_company = Company(
            id=1,
            name="Empresa de Prueba",
            short_name="test_company",
            logo_file="test_logo.png"
        )
        self.profile_service.get_company_by_short_name.return_value = self.test_company

        # Registrar la vista
        view = LoginView.as_view("login", profile_service=self.profile_service)
        self.app.add_url_rule("/<company_short_name>/login", view_func=view, methods=["GET", "POST"])

        # Registrar un endpoint temporal para el test
        @self.app.route("/test_company/chat")
        def chat():
            return jsonify({"message": "Bienvenido al chat"}), 200

    @patch("views.login_view.render_template")
    def test_get_and_post_invalid_company(self, mock_render):
        self.profile_service.get_company_by_short_name.return_value = None
        response = self.client.get("/test_company/login")
        assert response.status_code == 404

        response = self.client.post("/test_company/login",
                                    data={"email": "fer", "password": "123456"},
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 404

    @patch("views.login_view.render_template")
    def test_get_login_page(self, mock_render_template):
        mock_render_template.return_value = "<html><body><h1>Login Page</h1></body></html>"
        response = self.client.get("/test_company/login")

        mock_render_template.assert_called_once_with(
            "login.html",
            company=self.test_company,
            company_short_name='test_company'
        )

        assert response.status_code == 200
        assert b"<h1>Login Page</h1>" in response.data

    @patch("views.login_view.render_template")
    def test_post_with_error(self, mock_render_template):
        self.profile_service.login.return_value = {'error': 'login error'}
        mock_render_template.return_value = "<html><body><h1>Login Page</h1></body></html>"
        response = self.client.post("/test_company/login",
                                    data={"email": "fer", "password": "123456"},
                                    content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
            "login.html",
            company=self.test_company,
            company_short_name='test_company',
            form_data={"email": "fer", "password": "123456"},
            alert_message='login error'
        )
        assert response.status_code == 400

    def test_post_successful_login(self):
        self.profile_service.login.return_value = {"message": "Login exitoso"}
        response = self.client.post("/test_company/login",
                                    data={"email": "test@email.com", "password": "password"},
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 302  # Redirección exitosa
        assert response.location == "/test_company/chat?company_short_name=test_company"


    @patch("views.login_view.render_template")
    def test_post_unexpected_error(self, mock_render_template):
        """Prueba que se maneje correctamente un error inesperado."""
        self.profile_service.login.side_effect = Exception("Unexpected error")
        mock_render_template.return_value = "<html><body><h1>Error Page</h1></body></html>"
        response = self.client.post("/test_company/login",
                                    data={"email": "test@mail.com", "password": "any"},
                                    content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
            "error.html",
            company=self.test_company,
            company_short_name='test_company',
            message="Ha ocurrido un error inesperado."
        )
        assert response.status_code == 500