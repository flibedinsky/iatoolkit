# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import base64
from unittest.mock import MagicMock, patch

import pytest
from sib_api_v3_sdk.rest import ApiException

from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.infra.brevo_mail_app import BrevoMailApp


class TestBrevoMailApp:

    def setup_method(self):
        self.app = BrevoMailApp()
        self.provider_config = {
            "api_key": "dummy-api-key",
            "sender_email": "ia@test.com",
            "sender_name": "IA Toolkit",
        }
        self.sender = {'email': 'ia@iatoolkit.com', 'name': 'IA Toolkit'}


    # -------------------
    # _init_brevo
    # -------------------

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.TransactionalEmailsApi")
    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.ApiClient")
    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.Configuration")
    def test_init_brevo(
        self, mock_cfg_cls, mock_client_cls, mock_api_cls
    ):
        """_init_brevo debe configurar Brevo y devolver el sender por defecto."""
        mock_cfg = MagicMock()
        mock_cfg_cls.return_value = mock_cfg

        returned_sender = self.app._init_brevo(self.provider_config)

        # Configuración de API key
        mock_cfg_cls.assert_called_once()

        # mail_api inicializado
        mock_client_cls.assert_called_once_with(mock_cfg)
        mock_api_cls.assert_called_once()


    # -------------------
    # _normalize_attachments
    # -------------------

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.SendSmtpEmailAttachment")
    def test_normalize_attachments_happy_path(self, mock_attachment_cls):
        """_normalize_attachments debe crear objetos SendSmtpEmailAttachment válidos."""
        attachments = [
            {
                "filename": "test.txt",
                "content": base64.b64encode(b"hello").decode("utf-8"),
            }
        ]

        result = self.app._normalize_attachments(attachments)

        assert result is not None
        assert len(result) == 1
        mock_attachment_cls.assert_called_once()
        kwargs = mock_attachment_cls.call_args.kwargs
        assert kwargs["name"] == "test.txt"
        # contenido sigue siendo base64 válido
        base64.b64decode(kwargs["content"], validate=True)

    def test_normalize_attachments_returns_none_when_empty(self):
        assert self.app._normalize_attachments(None) is None
        assert self.app._normalize_attachments([]) is None

    def test_normalize_attachments_missing_filename_raises(self):
        attachments = [
            {
                "content": base64.b64encode(b"hello").decode("utf-8"),
            }
        ]

        with pytest.raises(IAToolkitException) as exc:
            self.app._normalize_attachments(attachments)

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "falta 'filename'" in str(exc.value)

    def test_normalize_attachments_missing_content_raises(self):
        attachments = [
            {
                "filename": "test.txt",
            }
        ]

        with pytest.raises(IAToolkitException) as exc:
            self.app._normalize_attachments(attachments)

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "falta 'content'" in str(exc.value)

    def test_normalize_attachments_invalid_base64_raises(self):
        attachments = [
            {
                "filename": "test.txt",
                "content": "###not-base64###",
            }
        ]

        with pytest.raises(IAToolkitException) as exc:
            self.app._normalize_attachments(attachments)

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "base64 inválido" in str(exc.value)

    def test_normalize_attachments_empty_content_raises(self):
        attachments = [
            {
                "filename": "empty.txt",
                "content": base64.b64encode(b"").decode("utf-8"),
            }
        ]

        with pytest.raises(IAToolkitException) as exc:
            self.app._normalize_attachments(attachments)

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "está vacío" in str(exc.value)

    # -------------------
    # send_email
    # -------------------

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_success(self, mock_send_email_cls):
        """Envío exitoso: respuesta con message_id debe devolverse sin errores."""
        # Mock init de Brevo para no tocar red
        self.app._init_brevo = MagicMock(return_value={"email": "ia@test.com", "name": "IA Toolkit"})
        self.app.mail_api = MagicMock()

        mock_response = MagicMock()
        mock_response.message_id = "12345"
        self.app.mail_api.send_transac_email.return_value = mock_response

        response = self.app.send_email(
            provider_config=self.provider_config,
            to="user@test.com",
            subject="Subject",
            body="<p>Body</p>",
            sender=self.sender,
            attachments=None,
        )

        # _init_brevo llamado con provider_config y sender=None
        self.app._init_brevo.assert_called_once_with(self.provider_config)

        # Se construyó el email y se envió
        mock_send_email_cls.assert_called_once()
        self.app.mail_api.send_transac_email.assert_called_once()
        assert response == mock_response

    def test_send_email_invalid_provider_config_raises(self):
        """Sin api_key en provider_config debe lanzar MAIL_ERROR."""
        invalid_config = {
            "sender_email": "ia@test.com",
            "sender_name": "IA Toolkit",
        }

        with pytest.raises(IAToolkitException) as exc:
            self.app.send_email(
                provider_config=invalid_config,
                to="user@test.com",
                subject="Subject",
                sender=self.sender,
                body="<p>Body</p>",
            )

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "Invalid mail configuration for Brevo" in str(exc.value)

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_without_message_id_raises(self, mock_send_email_cls):
        """Debe fallar si la respuesta de la API no incluye message_id(s)."""
        self.app._init_brevo = MagicMock(return_value={"email": "ia@test.com", "name": "IA Toolkit"})
        self.app.mail_api = MagicMock()

        mock_response = MagicMock()
        # Sin message_id ni message_ids configurados
        self.app.mail_api.send_transac_email.return_value = mock_response

        with pytest.raises(IAToolkitException) as exc:
            self.app.send_email(
                provider_config=self.provider_config,
                to="user@test.com",
                subject="Subject",
                sender=self.sender,
                body="<p>Body</p>",
            )

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "Brevo no retornó message_id" in str(exc.value)

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_with_api_exception(self, mock_send_email_cls):
        """ApiException debe mapearse a MAIL_ERROR con mensaje descriptivo."""
        self.app._init_brevo = MagicMock(return_value={"email": "ia@test.com", "name": "IA Toolkit"})
        self.app.mail_api = MagicMock()
        self.app.mail_api.send_transac_email.side_effect = ApiException(status=500, reason="Internal error")

        with pytest.raises(IAToolkitException) as exc:
            self.app.send_email(
                provider_config=self.provider_config,
                to="user@test.com",
                subject="Subject",
                sender=self.sender,
                body="<p>Body</p>",
            )

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "Error Brevo" in str(exc.value)

    @patch("iatoolkit.infra.brevo_mail_app.sib_api_v3_sdk.SendSmtpEmail")
    def test_send_email_with_generic_exception(self, mock_send_email_cls):
        """Cualquier otra excepción debe mapearse a MAIL_ERROR genérico."""
        self.app._init_brevo = MagicMock(return_value={"email": "ia@test.com", "name": "IA Toolkit"})
        self.app.mail_api = MagicMock()
        self.app.mail_api.send_transac_email.side_effect = Exception("boom")

        with pytest.raises(IAToolkitException) as exc:
            self.app.send_email(
                provider_config=self.provider_config,
                to="user@test.com",
                subject="Subject",
                sender=self.sender,
                body="<p>Body</p>",
            )

        assert exc.value.error_type == IAToolkitException.ErrorType.MAIL_ERROR
        assert "No se pudo enviar correo: boom" in str(exc.value)