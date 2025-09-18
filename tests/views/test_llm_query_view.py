# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from repositories.models import ApiKey, Company
from services.query_service import QueryService
from views.llmquery_view import LLMQueryView
from datetime import datetime, timezone
from common.session_manager import SessionManager
from common.auth import IAuthentication

class TestLLMQueryView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.testing = True
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_key'

        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.query_service = MagicMock(spec=QueryService)
        self.iauthentication = MagicMock(spec=IAuthentication)

        self.iauthentication.verify.return_value = {
            'success': True,
            'company_id': 101,
            'external_user_id': 'test_user_id'
        }

        self.test_data = {
            "question": "¿Pregunta con error?",
            "files": []
        }

        @self.app.route('/login')
        def login():
            return "Login Page", 200

        # Configurar la vista
        view = LLMQueryView.as_view('llm_query',
                                    query_service=self.query_service,
                                    iauthentication=self.iauthentication)
        self.app.add_url_rule('/<company_short_name>/query', view_func=view)

        self.query_service.llm_query.return_value = {
            "answer": "Respuesta exitosa",
            "aditional_data": {}
        }

        # Mock values
        self.api_key = ApiKey(key="test_key", company_id=100)
        self.api_key.company = Company(id=100, name="Test Company", short_name="test_company")

        mock_session_values = {
            'user': {'id': 1, 'username': 'test_user'},
            'user_id': 1,
            'company_id': 100,
            'company_short_name': 'test_company',
            'last_activity': datetime.now(timezone.utc).timestamp()
        }

        # Mockear SessionManager.get
        mock_session_manager = MagicMock(spec=SessionManager)  # <- Mock de la clase
        mock_session_manager.get.side_effect = lambda key, default=None: mock_session_values.get(key, default)

        with patch('common.auth.SessionManager', new=mock_session_manager):
            with self.app.test_request_context():  # Necesario para Flask
                yield

    def test_post_success(self):
        api_data = {
            "question": "¿Cuál es el significado de la vida?",
            "external_user_id": "test_user_id",
            "files": ["archivo1.txt", "archivo2.txt"]
        }

        # Realizar la solicitud
        response = self.client.post(
            '/test_company/query',
            json=api_data
        )

        # Verificaciones
        assert response.status_code == 200
        assert response.json['answer'] == "Respuesta exitosa"

        self.query_service.llm_query.assert_called_once_with(
            company_short_name='test_company',
            local_user_id=None,
            external_user_id='test_user_id',
            question=api_data["question"],
            prompt_name= None,
            client_data={},
            files=api_data["files"]
        )


    def test_post_when_missing_data(self):
        response = self.client.post(
            '/test_company/query',
            json={}
        )

        assert response.status_code == 400
        assert response.json["error_message"] == "Cuerpo de la solicitud JSON inválido o faltante"


    def test_post_when_auth_error(self):
        self.iauthentication.verify.return_value = {'error_message': 'error in authentication'}
        response = self.client.post(
            '/test_company/query',
            json=self.test_data
        )

        assert response.status_code == 401
        assert response.json["error_message"] == 'error in authentication'


    def test_post_service_error(self):
        """Prueba el manejo de errores del servicio."""
        self.query_service.llm_query.return_value = {
            "error": True,
            "error_message": "Error de proceso"
        }

        response = self.client.post(
            '/test_company/query',
            json=self.test_data
        )

        assert response.status_code == 401
        assert response.json["error_message"] == "Error de proceso"

    @patch("views.llmquery_view.render_template")
    def test_post_unexpected_error(self, mock_render):
        self.query_service.llm_query.side_effect = Exception("Error inesperado")

        test_data = {
            "question": "¿Pregunta con error?",
            "files": []
        }

        response = self.client.post('/test_company/query',json=test_data)
        assert response.status_code == 500
