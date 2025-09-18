# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from services.query_service import QueryService
from services.prompt_manager_service import PromptService
from services.user_session_context_service import UserSessionContextService
from repositories.profile_repo import ProfileRepo
from common.exceptions import AppException
from repositories.models import Company, User
import base64
import json
import os


# Fixture para simular que los archivos de prompt siempre existen
@pytest.fixture(autouse=True)
def patch_os_path_exists():
    with patch("os.path.exists", return_value=True):
        yield


class TestQueryService:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Crea una instancia de QueryService con mocks de sus dependencias."""
        with patch.dict(os.environ, {"LLM_MODEL": "gpt-5"}):
            # Mock de todas las dependencias inyectadas
            self.document_service = MagicMock()
            self.llmquery_repo = MagicMock()
            self.profile_repo = MagicMock(spec=ProfileRepo)
            self.prompt_service = MagicMock(spec=PromptService)
            self.utility = MagicMock()
            self.llm_client = MagicMock()
            self.dispatcher = MagicMock()
            self.session_context = MagicMock(spec=UserSessionContextService)

            # Configurar el mock de utility para que simule correctamente la resolución del user_identifier
            def mock_resolve_user_identifier(external_user_id=None, local_user_id=0):
                if external_user_id and external_user_id.strip():
                    return external_user_id.strip()
                if local_user_id and local_user_id > 0:
                    return f'User_{local_user_id}'
                return ""

            self.utility.resolve_user_identifier.side_effect = mock_resolve_user_identifier

            # Configuración de Mocks comunes
            self.user = User(id=1, email='test@user.com')
            self.company = Company(id=100, name='Test Company', short_name='test_company')
            self.profile_repo.get_user_by_id.return_value = self.user
            self.profile_repo.get_company_by_id.return_value = self.company
            self.profile_repo.get_company_by_short_name.return_value = self.company

            # Simular datos de sesión que el ContextService habría guardado
            self.session_context.get_user_session_data.return_value = {
                'user_rol': 'lider',
                'user_name': 'session_user'
            }
            self.session_context.get_last_response_id.return_value = 'prev_response_id'

            # Simular una respuesta exitosa del LLM que incluye el response_id
            self.mock_llm_response = {
                "valid_response": True,
                "answer": "Respuesta de prueba del LLM",
                "aditional_data": {"clave": "valor"},
                "response_id": "new_llm_response_id"
            }
            self.llm_client.invoke.return_value = self.mock_llm_response
            self.llm_client.set_company_context.return_value = 'new_context_response_id'

            self.user_info = {'user_rol': 'lider', 'user_name': 'test_user'}
            self.dispatcher.get_user_info.return_value = self.user_info
            self.dispatcher.get_company_services.return_value = [{'name': 'service1'}]
            self.dispatcher.get_company_context.return_value = "Contexto específico de la empresa."
            self.prompt_service.get_system_prompt.return_value = "Template de prompt de sistema: {{ user_rol }}"
            self.utility.render_prompt_from_string.return_value = "Prompt de sistema renderizado: lider"

            # modelo por defecto
            self.utility.is_openai_model.return_value = True
            self.utility.is_gemini_model.return_value = False

            # Crear la instancia del servicio bajo prueba
            # Esta línea ahora se ejecutará dentro del contexto del patch
            self.service = QueryService(
                document_service=self.document_service,
                document_repo=MagicMock(),
                llmquery_repo=self.llmquery_repo,
                profile_repo=self.profile_repo,
                prompt_service=self.prompt_service,
                util=self.utility,
                llm=self.llm_client,
                dispatcher=self.dispatcher,
                session_context=self.session_context
            )

            # Contenido de archivo para pruebas de carga de archivos
            self.document_content = b'contenido del documento'
            self.base64_content = base64.b64encode(self.document_content)

    # --- Pruebas de validación de entrada ---
    def test_llm_query_fails_if_no_company(self):
        self.profile_repo.get_company_by_short_name.return_value = None
        result = self.service.llm_query(company_short_name='a_company', question="test", external_user_id="test_user")
        assert "No existe Company ID" in result["error_message"]

    def test_llm_query_fails_if_no_question_or_prompt(self):
        result = self.service.llm_query(company_short_name='a_company', external_user_id="test_user")
        assert "Hola, cual es tu pregunta?" in result["error_message"]

    def test_llm_query_fails_if_no_previous_response_id(self):
        """Verifica que la consulta falla si no hay un ID de respuesta previo en la sesión."""
        self.session_context.get_last_response_id.return_value = None
        self.llm_client.set_company_context.return_value = None
        result = self.service.llm_query(
            company_short_name='a_company',
            external_user_id="test_user",
            question="test"
        )
        assert "FATAL: No se encontró 'previous_response_id'" in result["error_message"]

    def test_llm_query_with_direct_question_successfully(self):
        """
        Verifica una consulta directa y la correcta gestión de los IDs de respuesta en sesión.
        """
        question_text = "¿Cuál es el estado de la cartera?"
        external_user_id = 'ext_user_1'

        result = self.service.llm_query(
            company_short_name='a_company',
            external_user_id=external_user_id,
            question=question_text
        )

        assert result["valid_response"] is True
        assert result["answer"] == "Respuesta de prueba del LLM"

        # Verificar obtención de datos de sesión y del ID de respuesta previo
        self.session_context.get_user_session_data.assert_called_once_with('test_company', external_user_id)
        self.session_context.get_last_response_id.assert_called_once_with('test_company', external_user_id)

        # Verificar que se guardó el nuevo ID de respuesta en la sesión
        self.session_context.save_last_response_id.assert_called_once_with(
            'test_company', external_user_id, 'new_llm_response_id'
        )

        # Verificar que la llamada a invoke usó el ID previo
        self.llm_client.invoke.assert_called_once()
        call_kwargs = self.llm_client.invoke.call_args.kwargs
        assert call_kwargs['previous_response_id'] == 'prev_response_id'

    def test_llm_query_with_prompt_name_merges_data_correctly(self):
        """
        Prueba que los datos de sesión se mezclan con los de la solicitud,
        y estos últimos tienen prioridad.
        """
        request_client_data = {'rut': '1-9', 'user_name': 'request_user'}
        external_user_id = 'ext_user_2'

        self.service.llm_query(
            company_short_name='a_company',
            external_user_id=external_user_id,
            prompt_name="analisis_cartera",
            client_data=request_client_data
        )

        self.llm_client.invoke.assert_called_once()
        call_kwargs = self.llm_client.invoke.call_args.kwargs

        # El user_id resuelto debe ser el ID externo
        resolved_user_id = external_user_id

        # La pregunta enviada a invoke debe ser un JSON que contiene los datos combinados
        expected_data = {
            'prompt': 'analisis_cartera',
            'data': {
                'user_rol': 'lider',  # de la sesión
                'user_name': 'request_user',  # de la request (sobrescribe el de la sesión)
                'rut': '1-9',  # de la request
                'user_id': resolved_user_id  # añadido por el servicio
            }
        }

        # Comparamos los diccionarios para evitar problemas con el orden de las claves
        actual_question_dict = json.loads(call_kwargs['question'])
        assert actual_question_dict == expected_data

    def test_initialize_llm_context_happy_path_external_user(self):
        """
        Prueba el flujo completo y exitoso de inicialización de contexto,
        incluyendo la limpieza y guardado en sesión.
        """
        external_user_id = 'ext_user_123'
        company_short_name = 'test_co'
        # self.profile_repo.get_company_by_short_name.return_value = self.company

        self.service.llm_init_context(
            company_short_name=company_short_name,
            external_user_id=external_user_id
        )

        # 1. Verificar que se limpió el contexto previo
        self.session_context.clear_all_context.assert_called_once_with(
            company_short_name=company_short_name,
            user_identifier=external_user_id
        )

        # 2. Verificar guardado de datos del usuario en la sesión
        self.session_context.save_user_session_data.assert_called_once_with(
            company_short_name, external_user_id, self.user_info
        )

        # 3. Verificar que el contexto fue enviado al LLM
        self.llm_client.set_company_context.assert_called_once()

        # 4. Verificar que el ID de respuesta del nuevo contexto se guardó en la sesión
        self.session_context.save_last_response_id.assert_called_once_with(
            company_short_name, external_user_id, 'new_context_response_id'
        )

    def test_initialize_llm_context_happy_path_external_user_and_gemini(self):
        self.utility.is_gemini_model.return_value = True

        response = self.service.llm_init_context(
            company_short_name='test_co',
            external_user_id='ext_user_123',
            model="gemini"
        )

        # Verificar que el contexto no fue enviado al LLM
        self.llm_client.set_company_context.assert_not_called()
        assert response == "gemini-context-initialized"


    def test_initialize_llm_context_for_local_user(self):
        """
        Verifica que el flujo funciona correctamente cuando se usa un ID de usuario local.
        """
        local_user_id = 10
        company_short_name = 'test_co'
        resolved_user_identifier = f'User_{local_user_id}'

        self.service.llm_init_context(
            company_short_name=company_short_name,
            local_user_id=local_user_id
        )

        # Verificar que la sesión se guardó usando el ID local como identificador
        self.session_context.save_user_session_data.assert_called_once_with(
            company_short_name, resolved_user_identifier, self.user_info
        )

        self.llm_client.set_company_context.assert_called_once()

    def test_initialize_llm_context_raises_exception_if_company_not_found(self):
        """
        Verifica que se lanza una excepción si la empresa no existe.
        """
        self.profile_repo.get_company_by_short_name.return_value = None

        with pytest.raises(AppException) as excinfo:
            self.service.llm_init_context(company_short_name='non_existent_co', external_user_id="test_user")

        assert excinfo.value.error_type == AppException.ErrorType.INVALID_NAME
        assert "Empresa no encontrada: non_existent_co" in str(excinfo.value)
        self.dispatcher.get_user_info.assert_not_called()
        self.llm_client.set_company_context.assert_not_called()

    def test_initialize_llm_context_propagates_exceptions(self):
        """
        Verifica que si un servicio dependiente falla, la excepción se propaga.
        """
        error_message = "Error de red en el dispatcher"
        self.dispatcher.get_user_info.side_effect = Exception(error_message)

        with pytest.raises(Exception) as excinfo:
            self.service.llm_init_context(company_short_name='test_co', external_user_id='user')

        assert str(excinfo.value) == error_message

    # --- Pruebas de manejo de archivos ---

    def test_load_files_for_context_handles_empty_content(self):
        files = [{'filename': 'doc.pdf', 'content': base64.b64encode(b'').decode('ascii')}]
        with pytest.raises(AppException) as excinfo:
            self.service.load_files_for_context(files)
        assert excinfo.value.error_type == AppException.ErrorType.PROMPT_ERROR
        assert 'Documento no tiene contenido' in str(excinfo.value)

    def test_load_files_for_context_handles_service_exception(self):
        self.document_service.file_to_txt.side_effect = Exception("Fallo de conversión")
        files = [{'filename': 'doc.pdf', 'content': self.base64_content.decode('ascii')}]
        with pytest.raises(AppException) as excinfo:
            self.service.load_files_for_context(files)
        assert excinfo.value.error_type == AppException.ErrorType.PROMPT_ERROR
        assert 'No se pudo crear prompt' in str(excinfo.value)

    def test_load_files_for_context_builds_correctly(self):
        self.document_service.file_to_txt.return_value = "Texto extraído del documento."
        files = [{'filename': 'doc.pdf', 'content': self.base64_content.decode('ascii')}]

        context = self.service.load_files_for_context(files)

        assert "A continuación encontraras una lista de documentos adjuntos" in context
        assert "Documento adjunto con nombre: 'doc.pdf'" in context
        assert "Contenido del documento:\nTexto extraído del documento." in context