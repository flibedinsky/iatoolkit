# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.models import UserFeedback, Company
from injector import inject
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.infra.google_chat_app import GoogleChatApp
from iatoolkit.infra.mail_app import MailApp  # <-- 1. Importar MailApp
import logging


class UserFeedbackService:
    @inject
    def __init__(self,
                 profile_repo: ProfileRepo,
                 google_chat_app: GoogleChatApp,
                 mail_app: MailApp):
        self.profile_repo = profile_repo
        self.google_chat_app = google_chat_app
        self.mail_app = mail_app

    def _send_google_chat_notification(self, space_name: str, message_text: str):
        """Envía una notificación de feedback a un espacio de Google Chat."""
        try:
            chat_data = {
                "type": "MESSAGE_TRIGGER",
                "space": {"name": space_name},
                "message": {"text": message_text}
            }
            chat_result = self.google_chat_app.send_message(message_data=chat_data)
            if not chat_result.get('success'):
                logging.warning(f"Error al enviar notificación a Google Chat: {chat_result.get('message')}")
        except Exception as e:
            logging.exception(f"Fallo inesperado al enviar notificación a Google Chat: {e}")

    def _send_email_notification(self, destination_email: str, company_name: str, message_text: str):
        """Envía una notificación de feedback por correo electrónico."""
        try:
            subject = f"Nuevo Feedback de {company_name}"
            # Convertir el texto plano a un HTML simple para mantener los saltos de línea
            html_body = message_text.replace('\n', '<br>')
            self.mail_app.send_email(to=destination_email, subject=subject, body=html_body)
        except Exception as e:
            logging.exception(f"Fallo inesperado al enviar email de feedback: {e}")

    def _handle_notification(self, company: Company, message_text: str):
        """Lee la configuración de la empresa y envía la notificación al canal correspondiente."""
        feedback_params = company.parameters.get('user_feedback')
        if not isinstance(feedback_params, dict):
            logging.warning(f"No se encontró configuración de 'user_feedback' para la empresa {company.short_name}.")
            return

        # get channel and destination
        channel = feedback_params.get('channel')
        destination = feedback_params.get('destination')
        if not channel or not destination:
            logging.warning(f"Configuración 'user_feedback' incompleta para {company.short_name}. Faltan 'channel' o 'destination'.")
            return

        if channel == 'google_chat':
            self._send_google_chat_notification(space_name=destination, message_text=message_text)
        elif channel == 'email':
            self._send_email_notification(destination_email=destination, company_name=company.short_name, message_text=message_text)
        else:
            logging.warning(f"Canal de feedback '{channel}' no reconocido para la empresa {company.short_name}.")

    def new_feedback(self,
                     company_short_name: str,
                     message: str,
                     user_identifier: str,
                     rating: int = None) -> dict:
        try:
            # 1. Validar empresa
            company = self.profile_repo.get_company_by_short_name(company_short_name)
            if not company:
                return {'error': f'No existe la empresa: {company_short_name}'}

            # 2. Enviar notificación según la configuración de la empresa
            notification_text = (f"*Nuevo feedback de {company_short_name}*:\n"
                                 f"*Usuario:* {user_identifier}\n"
                                 f"*Mensaje:* {message}\n"
                                 f"*Calificación:* {rating if rating is not None else 'N/A'}")
            self._handle_notification(company, notification_text)

            # 3. Guardar el feedback en la base de datos (independientemente del éxito de la notificación)
            new_feedback_obj = UserFeedback(
                company_id=company.id,
                message=message,
                user_identifier=user_identifier,
                rating=rating
            )
            saved_feedback = self.profile_repo.save_feedback(new_feedback_obj)
            if not saved_feedback:
                logging.error(f"No se pudo guardar el feedback para el usuario {user_identifier} en la empresa {company_short_name}")
                return {'error': 'No se pudo guardar el feedback'}

            return {'message': 'Feedback guardado correctamente'}

        except Exception as e:
            logging.exception(f"Error crítico en el servicio de feedback: {e}")
            return {'error': str(e)}