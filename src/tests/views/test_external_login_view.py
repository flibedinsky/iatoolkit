import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
from iatoolkit.views.external_login_view import InitiateExternalChatView
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.prompt_manager_service import PromptService
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.services.onboarding_service import OnboardingService
from iatoolkit.services.auth_service import AuthService
from iatoolkit.repositories.models import Company

# --- Constantes para los Tests ---
MOCK_COMPANY_SHORT_NAME = "test-comp"
MOCK_EXTERNAL_USER_ID = "ext-user-123"


class TestExternalLoginFlow:
    """
    Suite de tests unificada para el flujo de login externo, que ahora crea una sesión web.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.app = Flask(__name__)
        self.app.testing = True
        self.client = self.app.test_client()

        # Mocks para todos los servicios
        self.mock_iauthentication = MagicMock(spec=AuthService)
        self.mock_branding_service = MagicMock(spec=BrandingService)
        self.mock_profile_service = MagicMock(spec=ProfileService)
        self.mock_onboarding_service = MagicMock(spec=OnboardingService)
        self.mock_query_service = MagicMock(spec=QueryService)
        self.mock_prompt_service = MagicMock(spec=PromptService)

        # Configuración común de mocks
        self.mock_company = Company(id=1, name="Test Company", short_name=MOCK_COMPANY_SHORT_NAME)
        self.mock_profile_service.get_company_by_short_name.return_value = self.mock_company
        self.mock_iauthentication.verify.return_value = {"success": True}

        # Registrar la vista
        initiate_view = InitiateExternalChatView.as_view(
            'initiate_external_chat',
            iauthentication=self.mock_iauthentication,
            branding_service=self.mock_branding_service,
            profile_service=self.mock_profile_service,
            onboarding_service=self.mock_onboarding_service,
            query_service=self.mock_query_service,
            prompt_service=self.mock_prompt_service,
        )
        self.app.add_url_rule('/<company_short_name>/initiate_external_chat', view_func=initiate_view, methods=['POST'])

        @self.app.route('/<company_short_name>/login', endpoint='login')
        def dummy_login(company_short_name): return "Heavy lifting page"

    @patch('iatoolkit.views.external_login_view.render_template')
    def test_initiate_external_chat_fast_path(self, mock_render):
        """Prueba el CAMINO RÁPIDO para un usuario externo."""
        self.mock_query_service.prepare_context.return_value = {'rebuild_needed': False}
        mock_render.return_value = "OK"

        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 200
        self.mock_iauthentication.verify.assert_called_once()
        self.mock_profile_service.create_external_user_session.assert_called_once()
        self.mock_query_service.prepare_context.assert_called_once_with(
            company_short_name=MOCK_COMPANY_SHORT_NAME,
            user_identifier=MOCK_EXTERNAL_USER_ID
        )
        mock_render.assert_called_once()
        assert mock_render.call_args[0][0] == 'chat.html'
        self.mock_query_service.finalize_context_rebuild.assert_not_called()

    @patch('iatoolkit.views.external_login_view.render_template')
    def test_initiate_external_chat_slow_path(self, mock_render):
        """Prueba el CAMINO LENTO para un usuario externo."""
        self.mock_query_service.prepare_context.return_value = {'rebuild_needed': True}
        mock_render.return_value = "OK"

        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 200
        self.mock_query_service.prepare_context.assert_called_once()
        mock_render.assert_called_once()
        assert mock_render.call_args[0][0] == 'onboarding_shell.html'

    def test_initiate_fails_if_no_external_user_id(self):
        """Prueba el fallo si el `external_user_id` no viene en el JSON."""
        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'other_data': 'value'}  # No external_user_id
        )

        assert response.status_code == 400
        assert 'Falta external_user_id' in response.json['error']
        self.mock_iauthentication.verify.assert_not_called()

    def test_initiate_fails_if_company_not_found(self):
        """Prueba el fallo si la compañía no existe."""
        self.mock_profile_service.get_company_by_short_name.return_value = None

        response = self.client.post(
            f'/nonexistent-company/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 404
        assert 'Empresa no encontrada' in response.json['error']
        self.mock_iauthentication.verify.assert_not_called()

    def test_initiate_fails_on_authentication_failure(self):
        """Prueba el fallo si la autenticación de API-Key falla."""
        self.mock_iauthentication.verify.return_value = {"success": False, "error": "Invalid API Key"}

        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 401
        assert response.json['error'] == 'Invalid API Key'
        self.mock_query_service.prepare_context.assert_not_called()

    def test_fast_path_handles_downstream_exception(self):
        """Prueba que el camino rápido maneja excepciones al obtener datos (ej. prompts)."""
        self.mock_query_service.prepare_context.return_value = {'rebuild_needed': False}
        # Simular un error tardío en el flujo
        self.mock_prompt_service.get_user_prompts.side_effect = Exception("Database connection lost")

        response = self.client.post(
            f'/{MOCK_COMPANY_SHORT_NAME}/initiate_external_chat',
            json={'external_user_id': MOCK_EXTERNAL_USER_ID}
        )

        assert response.status_code == 500
        assert 'Error interno al iniciar el chat' in response.json['error']
        assert 'Database connection lost' in response.json['error']