# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from infra.mail_app import MailApp
from injector import inject
from pathlib import Path
from common.exceptions import AppException
import base64

TEMP_DIR = Path("static/temp")

class MailService:
    @inject
    def __init__(self, mail_app: MailApp):
        self.mail_app = mail_app

    def _read_token_bytes(self, token: str) -> bytes:
        # Defensa simple contra path traversal
        if not token or "/" in token or "\\" in token or token.startswith("."):
            raise AppException(AppException.ErrorType.MAIL_ERROR,
                               "attachment_token inválido")
        path = TEMP_DIR / token
        if not path.is_file():
            raise AppException(AppException.ErrorType.MAIL_ERROR,
                               f"Adjunto no encontrado: {token}")
        return path.read_bytes()

    def send_mail(self, **kwargs):
        from_email = kwargs.get('from_email', 'iatoolkit@iatoolkit.com')
        recipient = kwargs.get('recipient')
        subject = kwargs.get('subject')
        body = kwargs.get('body')
        attachments = kwargs.get('attachments')

        # Normalizar a payload de MailApp (name + base64 content)
        norm_attachments = []
        for a in attachments or []:
            if a.get("attachment_token"):
                raw = self._read_token_bytes(a["attachment_token"])
                norm_attachments.append({
                    "filename": a["filename"],
                    "content": base64.b64encode(raw).decode("utf-8"),
                })
            else:
                # asumo que ya viene un base64
                norm_attachments.append({
                    "filename": a["filename"],
                    "content": a["content"]
                })

        self.sender = {"email": from_email, "name": "IAToolkit"}

        response = self.mail_app.send_email(
            sender=self.sender,
            to=recipient,
            subject=subject,
            body=body,
            attachments=norm_attachments)

        return 'mail enviado'
