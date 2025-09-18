# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from common.auth import IAuthentication
from views.external_login_view import ExternalLoginView
from services.query_service import QueryService


class TestExternalLoginView:
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
        self.iauthentication = MagicMock(spec=IAuthentication)
        self.query_service = MagicMock(spec=QueryService)

        self.iauthentication.verify.return_value = {"success": True}

        # Registrar la vista
        view = ExternalLoginView.as_view("external_login", 
                                         query_service=self.query_service,
                                        iauthentication=self.iauthentication)
        self.app.add_url_rule("/<company_short_name>/external_login/<external_user_id>", 
                             view_func=view, methods=["GET"])

    def test_get_with_valid_parameters(self):
        """Test que verifica que la vista funciona con parámetros válidos"""
        response = self.client.get("/test_company/external_login/user123")

        assert response.status_code == 200
        self.iauthentication.verify.assert_called_once_with("test_company", "user123")
        self.query_service.llm_init_context.assert_called_once_with(
            company_short_name="test_company",
            external_user_id="user123"
        )

    def test_get_with_authentication_failure(self):
        """Test que verifica el manejo de fallos de autenticación"""
        self.iauthentication.verify.return_value = {"success": False, "error": "Invalid credentials"}

        response = self.client.get("/test_company/external_login/user123")

        assert response.status_code == 401
        assert b"Invalid credentials" in response.data

    def test_get_with_service_exception(self):
        """Test que verifica el manejo de excepciones del servicio"""
        self.query_service.llm_init_context.side_effect = Exception("Service error")

        response = self.client.get("/test_company/external_login/user123")

        assert response.status_code == 500
        assert b"Service error" in response.data

    def test_get_with_different_company_and_user(self):
        """Test que verifica que funciona con diferentes combinaciones de company y user"""
        response = self.client.get("/maxxa/external_login/employee456")

        assert response.status_code == 200
        self.iauthentication.verify.assert_called_once_with("maxxa", "employee456")
        self.query_service.llm_init_context.assert_called_once_with(
            company_short_name="maxxa",
            external_user_id="employee456"
        )

    def test_get_with_special_characters_in_parameters(self):
        """Test que verifica el manejo de caracteres especiales en los parámetros"""
        response = self.client.get("/test-company/external_login/user-123")

        assert response.status_code == 200
        self.iauthentication.verify.assert_called_once_with("test-company", "user-123")
        self.query_service.llm_init_context.assert_called_once_with(
            company_short_name="test-company",
            external_user_id="user-123"
        )

    @patch('views.external_login_view.logging')
    def test_get_logs_exception_when_service_fails(self, mock_logging):
        """Test que verifica que se registra la excepción cuando falla el servicio"""
        self.query_service.llm_init_context.side_effect = Exception("Database connection failed")

        response = self.client.get("/test_company/external_login/user123")

        assert response.status_code == 500
        mock_logging.exception.assert_called_once()
        # Verificar que el mensaje de log contiene la información correcta
        call_args = mock_logging.exception.call_args[0][0]
        assert "test_company" in call_args
        assert "Database connection failed" in call_args