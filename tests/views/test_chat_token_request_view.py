# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from flask import Flask
from unittest.mock import MagicMock
from views.chat_token_request_view import ChatTokenRequestView
from services.jwt_service import JWTService
from repositories.profile_repo import ProfileRepo

# --- Constantes de Prueba ---
VALID_API_KEY_VALUE = "test-api-key-123"
MOCK_AUTH_COMPANY_ID = 100
MOCK_AUTH_COMPANY_SHORT_NAME = "authcomp"
MOCK_EXTERNAL_USER_ID = "ext-user-456"
GENERATED_TEST_JWT = "test.jwt.token.string"
JWT_EXPIRATION_CONFIG_VALUE = 1800  # 30 minutos para test


class TestChatTokenRequestView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.testing = True
        app.config['JWT_EXPIRATION_SECONDS_CHAT'] = JWT_EXPIRATION_CONFIG_VALUE
        # Aseguramos que current_app.config esté disponible en el init de la vista
        # app.app_context().push() # No es necesario aquí si la vista se instancia dentro del contexto en setup
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = self.create_app()
        # Es importante que la vista se registre y se cree el cliente de prueba
        # dentro de un contexto de aplicación para que current_app esté disponible.
        with self.app.app_context():
            self.profile_repo = MagicMock(spec=ProfileRepo)
            self.jwt_service = MagicMock(spec=JWTService)

            # register the view
            view_func = ChatTokenRequestView.as_view(
                'chat-token',  # Nombre del endpoint para el test
                profile_repo=self.profile_repo,
                jwt_service=self.jwt_service
            )
            self.app.add_url_rule('/auth/chat_token', view_func=view_func, methods=['POST'])

        self.client = self.app.test_client()

    def test_post_no_api_key_header(self):
        response = self.client.post('/auth/chat_token', json={
            "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
            "external_user_id": MOCK_EXTERNAL_USER_ID
        })
        assert response.status_code == 401
        assert response.json == {"error": "API Key faltante o mal formada en el header Authorization"}

    def test_post_malformed_api_key_header(self):
        """Prueba POST con header de Authorization mal formado."""
        response = self.client.post('/auth/chat_token',
                                    headers={"Authorization": "NotBearerKey"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 401
        assert response.json == {"error": "API Key faltante o mal formada en el header Authorization"}

    def test_post_invalid_or_inactive_api_key(self):
        """Prueba POST con una API Key inválida o inactiva."""
        self.profile_repo.get_active_api_key_entry.return_value = None
        response = self.client.post('/auth/chat_token', headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 401
        assert response.json == {"error": "API Key inválida o inactiva"}
        self.profile_repo.get_active_api_key_entry.assert_called_once_with(VALID_API_KEY_VALUE)

    def test_post_api_key_without_company_association(self):
        """Prueba POST con API Key válida pero sin compañía asociada (error de datos)."""
        mock_api_key_entry = MagicMock()
        mock_api_key_entry.company = None
        mock_api_key_entry.company_id = None
        self.profile_repo.get_active_api_key_entry.return_value = mock_api_key_entry

        response = self.client.post('/auth/chat_token', headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 500
        assert response.json == {"error": "Error interno del servidor al verificar API Key"}

    def test_post_api_key_validation_internal_exception(self):
        """Prueba POST donde la validación de API Key lanza una excepción."""
        self.profile_repo.get_active_api_key_entry.side_effect = Exception("Database connection error")
        response = self.client.post('/auth/chat_token', headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 500
        assert response.json == {"error": "Error interno del servidor al validar API Key"}

    def _setup_successful_auth(self):
        """Helper para configurar una autenticación de API Key exitosa."""
        mock_company_obj = MagicMock()
        mock_company_obj.short_name = MOCK_AUTH_COMPANY_SHORT_NAME

        mock_api_key_entry_obj = MagicMock()
        mock_api_key_entry_obj.company_id = MOCK_AUTH_COMPANY_ID
        mock_api_key_entry_obj.company = mock_company_obj
        self.profile_repo.get_active_api_key_entry.return_value = mock_api_key_entry_obj

    def test_post_missing_json_body(self):
        """Prueba POST con header de autenticación válido pero sin cuerpo JSON."""
        self._setup_successful_auth()
        response = self.client.post('/auth/chat_token',
                                    headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={},
                                    content_type="application/json")
        assert response.status_code == 400
        assert response.json == {"error": "Cuerpo de la solicitud JSON faltante"}

    @pytest.mark.parametrize("payload", [
        {"external_user_id": MOCK_EXTERNAL_USER_ID},  # Falta company_short_name
        {"company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME},  # Falta external_user_id
    ])
    def test_post_missing_fields_in_json_payload(self, payload):
        """Prueba POST con campos faltantes en el payload JSON."""
        self._setup_successful_auth()
        response = self.client.post('/auth/chat_token',
                                    headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json=payload)
        assert response.status_code == 401
        assert response.json['error'] == "Faltan 'company_short_name' o 'external_user_id' en el cuerpo de la solicitud"

    def test_post_api_key_company_mismatch_with_payload(self):
        """Prueba POST donde la compañía de la API Key no coincide con la del payload."""
        self._setup_successful_auth()  # API Key es de MOCK_AUTH_COMPANY_SHORT_NAME

        mismatched_company_short_name = "othercomp"
        response = self.client.post('/auth/chat_token',
                                    headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": mismatched_company_short_name,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 403
        assert response.json == {
            "error": f"API Key no autorizada para generar tokens para la compañía '{mismatched_company_short_name}'"}

    def test_post_successful_token_generation(self):
        """Prueba una generación de token exitosa."""
        self._setup_successful_auth()
        self.jwt_service.generate_chat_jwt.return_value = GENERATED_TEST_JWT

        response = self.client.post('/auth/chat_token', headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })

        assert response.status_code == 200
        assert response.json == {"chat_jwt": GENERATED_TEST_JWT}
        self.jwt_service.generate_chat_jwt.assert_called_once_with(
            company_id=MOCK_AUTH_COMPANY_ID,
            company_short_name=MOCK_AUTH_COMPANY_SHORT_NAME,
            external_user_id=MOCK_EXTERNAL_USER_ID,
            expires_delta_seconds=JWT_EXPIRATION_CONFIG_VALUE
        )

    def test_post_jwt_service_fails_to_generate_token(self):
        """Prueba el caso donde JWTService no puede generar un token."""
        self._setup_successful_auth()
        self.jwt_service.generate_chat_jwt.return_value = None  # Simula fallo en la generación

        response = self.client.post('/auth/chat_token', headers={"Authorization": f"Bearer {VALID_API_KEY_VALUE}"},
                                    json={
                                        "company_short_name": MOCK_AUTH_COMPANY_SHORT_NAME,
                                        "external_user_id": MOCK_EXTERNAL_USER_ID
                                    })
        assert response.status_code == 500
        assert response.json == {"error": "No se pudo generar el token de chat"}