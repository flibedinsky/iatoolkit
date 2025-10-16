# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.views.signup_view import SignupView
from iatoolkit.repositories.models import Company


class TestSignupView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.testing = True

        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y los mocks antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.profile_service = MagicMock(spec=ProfileService)
        self.branding_service = MagicMock(spec=BrandingService)
        self.test_company = Company(
            id=1,
            name="Empresa de Prueba",
            short_name="test_company"
        )
        self.profile_service.get_company_by_short_name.return_value = self.test_company

        # Registrar la vista
        view = SignupView.as_view("signup",
                                  profile_service=self.profile_service,
                                  branding_service=self.branding_service,)
        self.app.add_url_rule("/<company_short_name>/signup", view_func=view, methods=["GET", "POST"])

        # Añadir rutas dummy para que url_for() no falle en las pruebas
        @self.app.route("/<company_short_name>/")
        def index(company_short_name):
            return "Página de índice", 200

        @self.app.route("/<company_short_name>/verify/<token>")
        def verify_account(company_short_name, token):
            return "Página de verificación", 200

    @patch("iatoolkit.views.signup_view.render_template")
    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_get_when_invalid_company(self, mock_serializer, mock_render):
        mock_serializer.return_value.loads.return_value = "nonexistent@email.com"
        self.profile_service.get_company_by_short_name.return_value = None
        response = self.client.get("/test_company/signup")
        assert response.status_code == 404

    @patch("iatoolkit.views.signup_view.render_template")
    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_post_when_invalid_company(self, mock_serializer, mock_render):
        mock_serializer.return_value.loads.return_value = "nonexistent@email.com"
        self.profile_service.get_company_by_short_name.return_value = None
        response = self.client.post("/test_company/signup",
                                    data={},
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 404

    @patch("iatoolkit.views.signup_view.render_template")
    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_get_signup_page(self, mock_serializer, mock_render_template):
        mock_serializer.return_value.loads.return_value = "nonexistent@email.com"
        mock_render_template.return_value = "<html><body><h1>Signup Page</h1></body></html>"
        response = self.client.get("/test_company/signup")

        assert response.status_code == 200

    @patch("iatoolkit.views.signup_view.render_template")
    @patch("iatoolkit.views.signup_view.url_for")
    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_post_with_error(self, mock_serializer, mock_url_for, mock_render_template):
        mock_serializer.return_value.loads.return_value = "nonexistent@email.com"
        mock_url_for.return_value = 'http://verification'
        mock_render_template.return_value = "<html><body></body></html>"
        self.profile_service.signup.return_value = \
            {'error': 'user exists'}

        response = self.client.post("/test_company/signup",
                                    data={
                                        "first_name": "Juan",
                                        "last_name": "Perez",
                                        "email": "test@email.com",
                                        "password": "password123",
                                        "confirm_password": "password123"
                                    },
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 400

    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_post_when_ok(self, mock_serializer_class):
        """Prueba un POST exitoso que crea un usuario y establece el mensaje en sesión."""
        # Configurar mocks
        success_message = "¡Cuenta creada! Revisa tu correo para verificarla."
        mock_serializer_class.return_value.dumps.return_value = 'some-secure-token'
        self.profile_service.signup.return_value = {"message": success_message}

        # Usar el cliente de prueba dentro de un contexto para manejar la sesión
        with self.client:
            response = self.client.post("/test_company/signup",
                                        data={
                                            "first_name": "Juan",
                                            "last_name": "Perez",
                                            "email": "juan@email.com",
                                            "password": "password123",
                                            "confirm_password": "password123"
                                        })

            # 1. Verificar que se produjo una redirección (302) a la página correcta
            assert response.status_code == 302
            assert response.location == "/test_company/"

            # 2. Abrir la sesión resultante para verificar su contenido
            with self.client.session_transaction() as sess:
                assert sess['alert_message'] == success_message
                assert sess['alert_icon'] == 'success'

    @patch("iatoolkit.views.signup_view.render_template")
    @patch("iatoolkit.views.signup_view.URLSafeTimedSerializer")
    def test_post_unexpected_error(self, mock_serializer_class, mock_render_template):
        # Corregir el mock: la vista llama a .dumps() para crear el token.
        # Es aquí donde debemos simular el error.
        mock_serializer_class.return_value.dumps.side_effect = Exception('an error')

        response = self.client.post("/test_company/signup",
                                    data={
                                        "first_name": "Juan",
                                        "last_name": "Perez",
                                        "email": "juan@email.com",
                                        "password": "password123",
                                        "confirm_password": "password123"
                                    },
                                    content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
            "error.html",
            company=self.test_company,
            company_short_name='test_company',
            message="Ha ocurrido un error inesperado."
        )
        assert response.status_code == 500