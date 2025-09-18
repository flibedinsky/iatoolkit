# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from common.exceptions import AppException
from infra.mail_app import MailApp
import os

class TestMailApp:
    @classmethod
    def setup_class(cls):
        cls.patcher = patch.dict(os.environ, {"BREVO_API_KEY": "my-api-key"})
        cls.patcher.start()

    def setup_method(self):
        # Crear una instancia de MailApp simulada
        self.mail_app = MailApp()

        # Mock de la API de correos transaccionales
        self.mock_mail_api = MagicMock()
        self.mail_app.mail_api = self.mock_mail_api

    def teardown_method(self):
        self.patcher.stop()

    @patch("infra.mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_success(self, mock_send_smtp_email):
        """Prueba el envío exitoso del correo electrónico."""
        # Simular una respuesta exitosa de la API
        mock_response = MagicMock()
        mock_response.message_id = "100"
        self.mock_mail_api.send_transac_email.return_value = mock_response

        # Llamar al método `send_email`
        response = self.mail_app.send_email(
            to="test@domain.com",
            subject="Test Subject",
            body="<p>This is a test email</p>"
        )

        # Verificaciones
        self.mock_mail_api.send_transac_email.assert_called_once()
        assert response == mock_response

    @patch("infra.mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_when_api_error(self, mock_send_smtp_email):
        """Prueba el envío exitoso del correo electrónico."""
        # Simular una respuesta exitosa de la API
        mock_response = MagicMock()
        self.mock_mail_api.send_transac_email.return_value = mock_response

        with pytest.raises(AppException) as excinfo:
            response = self.mail_app.send_email(
                to="test@domain.com",
                subject="Test Subject",
                body="<p>This is a test email</p>"
            )

        # Verificar que la excepción es la esperada
        assert excinfo.value.error_type == AppException.ErrorType.MAIL_ERROR
        assert "Brevo no retornó message_id" in str(excinfo.value)


    @patch("infra.mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_with_error(self, mock_send_smtp_email):
        """Prueba el manejo de errores cuando se lanza una excepción."""
        # Simular que la API lanza una excepción
        self.mock_mail_api.send_transac_email.side_effect = Exception("API error")

        with pytest.raises(AppException) as excinfo:
            self.mail_app.send_email(
                to="test@domain.com",
                subject="Test Subject",
                body="<p>This is a test email</p>"
            )

        # Verificar que la excepción es la esperada
        assert excinfo.value.error_type == AppException.ErrorType.MAIL_ERROR
        assert "No se pudo enviar correo: API error" in str(excinfo.value)

    def test_initial_configuration(self):
        """Prueba la configuración inicial de MailApp."""
        with patch("os.getenv", return_value="mocked_api_key") as mock_getenv:
            mail_app = MailApp()

            # Verificar que la configuración fue inicializada correctamente
            assert mail_app.configuration.api_key['api-key'] == "mocked_api_key"
            assert mail_app.sender == {'email': 'ia@iatoolkit.com', 'name': 'IA Toolkit'}

            # Asegurar que os.getenv fue llamado para recuperar la clave de API
            mock_getenv.assert_called_once_with("BREVO_API_KEY")
