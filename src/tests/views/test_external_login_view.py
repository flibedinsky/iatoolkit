
import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.views.external_login_view import InitiateExternalChatView, ExternalChatLoginView
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.prompt_manager_service import PromptService
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.services.onboarding_service import OnboardingService
from iatoolkit.services.jwt_service import JWTService
from iatoolkit.common.auth import IAuthentication
from iatoolkit.repositories.models import Company

# --- Constantes para los Tests ---
MOCK_COMPANY_SHORT_NAME = "test-comp"
MOCK_EXTERNAL_USER_ID = "ext-user-123"
MOCK_INIT_TOKEN = "a-fake-but-valid-initiation-token"
MOCK_SESSION_TOKEN = "a-long-lived-session-token"


class TestInitiateExternalChatView:
    """Pruebas para la vista InitiateExternalChatView con el flujo de token de iniciación."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)
        self.app.testing = True
        self.client = self.app.test_client()

        self.mock_iauthentication = MagicMock(spec=IAuthentication)
        self.mock_branding_service = MagicMock(spec=BrandingService)
        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_onboarding_service = MagicMock(spec=OnboardingService)
        self.mock_jwt_service = MagicMock(spec=JWTService)

        self.mock_company = Company(id=1, name="Test Company", short_name=MOCK_COMPANY_SHORT_NAME)
        self.mock_profile_service.get_company_by_short_name.return_value = self.mock_company
        self.mock_branding_service.get_company_branding.return_value = {}

        view_func = InitiateExternalChatView.as_view(
            'initiate_external_chat',
            iauthentication=self.mock_iauthentication,
            branding_service=self.mock_branding_service,
            profile_service=self.mock_profile_service,
            onboarding_service=self.mock_onboarding_service,
            jwt_service=self.mock_jwt_service
        )
        self.app.add_url_rule('/<company_short_name>/initiate_external_chat', view_func=view_func, methods=['POST'])

        @self.app.route('/<company_short_name>/external_login', endpoint='external_login')
        def dummy_external_login(company_short_name): return "OK"

    @patch('iatoolkit.views.external_login_view.render_template')
    def test_initiate_success(self, mock_render):
        """Prueba que una iniciación exitosa genera un token y devuelve el shell."""
        self.mock_iauthentication.verify.return_value = {"success": True}
        self.mock_onboarding_service.get_onboarding_cards.return_value = [{'title': 'Card'}]
        self.mock_jwt_service.generate_chat_jwt.return_value = MOCK_INIT_TOKEN
        mock_render.return_value = "<html>Shell Page</html>"

        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 200
        # Verificar que se generó el token de iniciación
        self.mock_jwt_service.generate_chat_jwt.assert_called_once_with(
            company_id=self.mock_company.id,
            company_short_name=self.mock_company.short_name,
            external_user_id=MOCK_EXTERNAL_USER_ID,
            expires_delta_seconds=180
        )
        # Verificar que se renderizó la plantilla con la URL firmada
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args[1]
        assert 'iframe_src_url' in call_kwargs
        assert f"init_token={MOCK_INIT_TOKEN}" in call_kwargs['iframe_src_url']

    def test_initiate_auth_failure(self):
        """Prueba que una autenticación fallida devuelve un error 401."""
        self.mock_iauthentication.verify.return_value = {"success": False, "error": "Invalid API Key"}
        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )
        assert response.status_code == 401
        assert 'Invalid API Key' in response.json['error']


class TestExternalChatLoginView:
    """Pruebas para la vista de carga pesada (ExternalChatLoginView) con token de iniciación."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)
        self.app.testing = True

        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_query_service = MagicMock(spec=QueryService)
        self.mock_prompt_service = MagicMock(spec=PromptService)
        self.mock_iauthentication = MagicMock(spec=IAuthentication)
        self.mock_jwt_service = MagicMock(spec=JWTService)
        self.mock_branding_service = MagicMock(spec=BrandingService)

        self.mock_company = Company(id=1, name="Test Company", short_name=MOCK_COMPANY_SHORT_NAME)
        self.mock_profile_service.get_company_by_short_name.return_value = self.mock_company

        view_func = ExternalChatLoginView.as_view(
            'external_login',
            profile_service=self.mock_profile_service,
            query_service=self.mock_query_service,
            prompt_service=self.mock_prompt_service,
            branding_service=self.mock_branding_service,
            iauthentication=self.mock_iauthentication,
            jwt_service=self.mock_jwt_service
        )
        self.app.add_url_rule('/<company_short_name>/external_login', view_func=view_func, methods=['GET'])
        self.client = self.app.test_client()

    @patch('iatoolkit.views.external_login_view.render_template')
    def test_login_success(self, mock_render):
        """Prueba el flujo exitoso validando el token de iniciación."""
        # Arrange: Simular la validación exitosa del token de iniciación
        self.mock_jwt_service.validate_chat_jwt.return_value = {
            'external_user_id': MOCK_EXTERNAL_USER_ID,
            'company_short_name': MOCK_COMPANY_SHORT_NAME
        }
        # Simular la generación del token de sesión final
        self.mock_jwt_service.generate_chat_jwt.return_value = MOCK_SESSION_TOKEN
        self.mock_prompt_service.get_user_prompts.return_value = []
        self.mock_branding_service.get_company_branding.return_value = {}
        mock_render.return_value = "<html>Chat Page</html>"

        # Act: Llamar al endpoint con el token en la URL
        response = self.client.get(f'/{MOCK_COMPANY_SHORT_NAME}/external_login?init_token={MOCK_INIT_TOKEN}')

        # Assert
        assert response.status_code == 200
        # Verificar que se validó el token de iniciación
        self.mock_jwt_service.validate_chat_jwt.assert_called_once_with(MOCK_INIT_TOKEN, MOCK_COMPANY_SHORT_NAME)
        # Verificar que se generó el token de sesión final
        self.mock_jwt_service.generate_chat_jwt.assert_called_once_with(
            company_id=self.mock_company.id,
            company_short_name=self.mock_company.short_name,
            external_user_id=MOCK_EXTERNAL_USER_ID,
            expires_delta_seconds=3600 * 8
        )
        self.mock_query_service.llm_init_context.assert_called_once()
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args[1]
        assert call_kwargs['session_jwt'] == MOCK_SESSION_TOKEN

    def test_login_fails_with_invalid_init_token(self):
        """Prueba que la vista devuelve un error 401 si el token de iniciación es inválido."""
        # Arrange: Simular un fallo en la validación del token
        self.mock_jwt_service.validate_chat_jwt.return_value = None

        # Act
        response = self.client.get(f'/{MOCK_COMPANY_SHORT_NAME}/external_login?init_token=invalid-token')

        # Assert
        assert response.status_code == 401
        assert b"Token de iniciaci" in response.data

    def test_login_fails_without_init_token(self):
        """Prueba que la vista devuelve un error 401 si no se proporciona el token."""
        # Act
        response = self.client.get(f'/{MOCK_COMPANY_SHORT_NAME}/external_login') # Sin token
        # Assert
        assert response.status_code == 401
        assert b"Falta el token de iniciaci" in response.data