# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.views.change_password_view import ChangePasswordView
from itsdangerous import SignatureExpired
import os
from iatoolkit.repositories.models import Company



class TestChangePasswordView:
    @classmethod
    def setup_class(cls):
        cls.patcher = patch.dict(os.environ, {"PASS_RESET_KEY": "mocked_reset_key"})
        cls.patcher.start()

    @classmethod
    def teardown_class(cls):
        cls.patcher.stop()

    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y los mocks antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.profile_service = MagicMock(spec=ProfileService)
        self.test_company = Company(
            id=1,
            name="Empresa de Prueba",
            short_name="test_company"
        )
        self.profile_service.get_company_by_short_name.return_value = self.test_company

        # Registrar la vista
        view = ChangePasswordView.as_view("change_password", profile_service=self.profile_service)
        self.app.add_url_rule("/<company_short_name>/change_password/<token>", view_func=view, methods=["GET", "POST"])


    @patch("iatoolkit.views.change_password_view.render_template")
    def test_get_and_post_invalid_company(self, mock_render):
        self.profile_service.get_company_by_short_name.return_value = None
        response = self.client.get("/test_company/change_password/valid_token")
        assert response.status_code == 404

        response = self.client.post("/test_company/change_password/valid_token",
                                    data={
                                        "temp_code": "123456",
                                        "new_password": "password123",
                                        "confirm_password": "password456"
                                    },
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 404

    @patch("iatoolkit.views.change_password_view.render_template")
    def test_get_with_expired_token(self, mock_render_template):
        """Prueba GET con un token expirado."""
        # Configura el serializer para que lance una excepción SignatureExpired
        with patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer") as mock_serializer_class:
            mock_serializer = mock_serializer_class.return_value
            mock_serializer.loads.side_effect = SignatureExpired('error')

            mock_render_template.return_value = "<html><body><h1>Forgot Password</h1></body></html>"
            response = self.client.get("/test_company/change_password/expired_token")

            mock_render_template.assert_called_once_with(
                "forgot_password.html",
                alert_message="El enlace de cambio de contraseña ha expirado. Por favor, solicita uno nuevo."
            )
            assert response.status_code == 200

    @patch("iatoolkit.views.change_password_view.render_template")
    def test_get_with_valid_token(self, mock_render_template):
        """Prueba GET con un token válido."""
        with patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer") as mock_serializer_class:
            mock_serializer = mock_serializer_class.return_value
            mock_serializer.loads.return_value = "valid@email.com"

            mock_render_template.return_value = "<html><body><h1>Change Password</h1></body></html>"
            response = self.client.get("/test_company/change_password/valid_token")

            mock_render_template.assert_called_once_with(
                "change_password.html",
                company=self.test_company,
                company_short_name='test_company',
                token="valid_token",
                email="valid@email.com"
            )
            assert response.status_code == 200

    @patch("iatoolkit.views.change_password_view.render_template")
    @patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer")
    def test_post_with_expired_token(self, mock_serializer, mock_render_template):
        # Configura el serializer para que lance una excepción SignatureExpired
        mock_serializer.return_value.loads.side_effect = SignatureExpired('error')

        mock_render_template.return_value = "<html><body><h1>Forgot Password</h1></body></html>"
        response = self.client.post("/test_company/change_password/valid_token",
                                        data={
                                            "temp_code": "123456",
                                            "new_password": "password123",
                                            "confirm_password": "password456"
                                        },
                                        content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
            "forgot_password.html",
            company=self.test_company,
            company_short_name='test_company',
            alert_message="El enlace de cambio de contraseña ha expirado. Por favor, solicita uno nuevo."
        )
        assert response.status_code == 200

    @patch("iatoolkit.views.change_password_view.render_template")
    @patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer")
    def test_post_with_error(self, mock_serializer, mock_render_template):
        mock_serializer.return_value.return_value = "valid@email.com"
        mock_render_template.return_value = "<html><body></body></html>"
        self.profile_service.change_password.return_value = \
            {'error': 'password missmatch'}
        response = self.client.post("/test_company/change_password/valid_token",
                                        data={
                                            "temp_code": "123456",
                                            "new_password": "password123",
                                            "confirm_password": "password456"
                                        },
                                        content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
                "change_password.html",
            company=self.test_company,
            company_short_name='test_company',
                form_data={"temp_code": "123456", "new_password": "password123", "confirm_password": "password456"},
                alert_message='password missmatch',
                token='valid_token'
            )
        assert response.status_code == 400

    @patch("iatoolkit.views.change_password_view.render_template")
    @patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer")
    def test_post_ok(self, mock_serializer, mock_render_template):
        mock_serializer.return_value.return_value = "valid@email.com"
        mock_render_template.return_value = "<html><body></body></html>"
        self.profile_service.change_password.return_value = \
            {'message': 'password changed'}

        response = self.client.post("/test_company/change_password/valid_token",
                                    data={
                                        "temp_code": "123456",
                                        "new_password": "password123",
                                        "confirm_password": "password456"
                                    },
                                    content_type="application/x-www-form-urlencoded")

        mock_render_template.assert_called_once_with(
            "login.html",
            company=self.test_company,
            company_short_name='test_company',
            alert_icon='success',
            alert_message="Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión."
        )
        assert response.status_code == 200

    @patch("iatoolkit.views.change_password_view.render_template")
    @patch("iatoolkit.views.change_password_view.URLSafeTimedSerializer")
    def test_post_unexpected_error(self, mock_serializer, mock_render_template):
        mock_serializer.return_value.loads.return_value ='123'
        self.profile_service.change_password.side_effect = Exception('an error')
        response = self.client.post("/test_company/change_password/valid_token",
                                    data={
                                        "temp_code": "123456",
                                        "new_password": "password123",
                                        "confirm_password": "password456"
                                    },
                                    content_type="application/x-www-form-urlencoded")

        assert response.status_code == 500
