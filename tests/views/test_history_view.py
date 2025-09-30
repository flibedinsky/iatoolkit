# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from views.history_view import HistoryView
from services.history_service import HistoryService
from common.auth import IAuthentication


class TestHistoryView:
    @staticmethod
    def create_app():
        app = Flask(__name__)
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.history_service = MagicMock(spec=HistoryService)
        self.iauthentication = MagicMock(spec=IAuthentication)

        self.iauthentication.verify.return_value = {
            'success': True,
            'company_id': 101,
            'external_user_id': 'test_user_id'
        }

        # register the view
        self.history_view = HistoryView.as_view("history",
                                          history_service=self.history_service,
                                          iauthentication=self.iauthentication)
        self.app.add_url_rule('/<company_short_name>/history',
                              view_func=self.history_view,
                              methods=["POST"])

    def test_post_when_missing_data(self):
        """Test when no JSON data is provided"""
        response = self.client.post('/my_company/history',
                                    json={})

        assert response.status_code == 400
        assert response.json["error_message"] == "Cuerpo de la solicitud JSON inválido o faltante"
        self.history_service.get_history.assert_not_called()

    def test_post_when_invalid_json(self):
        """Test when invalid JSON is provided"""
        response = self.client.post('/my_company/history',
                                    data='invalid json',
                                    content_type='application/json')

        assert response.status_code == 400
        assert response.json["error_message"] == "Cuerpo de la solicitud JSON inválido o faltante"
        self.history_service.get_history.assert_not_called()

    def test_post_when_auth_error(self):
        """Test when authentication fails"""
        self.iauthentication.verify.return_value = {
            'success': False,
            'error_message': 'Usuario no autenticado'
        }

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 401
        assert response.json["error_message"] == 'Usuario no autenticado'
        self.history_service.get_history.assert_not_called()

    def test_post_when_missing_external_user_id(self):
        """Test when external_user_id is missing"""
        response = self.client.post('/my_company/history',
                                    json={})

        assert response.status_code == 400
        assert response.json["error_message"] == "Cuerpo de la solicitud JSON inválido o faltante"
        self.history_service.get_history.assert_not_called()

    def test_post_when_service_error(self):
        """Test when service returns an error"""
        self.history_service.get_history.return_value = {
            'error': 'Error al obtener historial'
        }

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 402
        assert response.json == {'error_message': 'Error al obtener historial'}

    def test_post_when_service_exception(self):
        """Test when service raises an exception"""
        self.history_service.get_history.side_effect = Exception('Service error')

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 500
        assert response.json["error_message"] == 'Service error'

    def test_post_when_ok_with_external_user_id(self):
        """Test successful request with external_user_id"""
        mock_history = {
            'success': True,
            'history': [
                {
                    'id': 1,
                    'question': 'Test question',
                    'answer': 'Test answer',
                    'created_at': '2024-01-15T10:30:00Z'
                }
            ],
            'count': 1
        }
        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 200
        assert response.json == mock_history

        # Verify service was called correctly
        self.history_service.get_history.assert_called_once_with(
            company_short_name='my_company',
            external_user_id='flibe',
            local_user_id=0
        )

    def test_post_when_ok_with_local_user_id(self):
        """Test successful request with local_user_id"""
        mock_history = {
            'success': True,
            'history': [
                {
                    'id': 1,
                    'question': 'Test question',
                    'answer': 'Test answer',
                    'created_at': '2024-01-15T10:30:00Z'
                }
            ],
            'count': 1
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={
                                        'external_user_id': 'flibe',
                                        'local_user_id': 123
                                    })

        assert response.status_code == 200
        assert response.json == mock_history

        # Verify service was called correctly
        self.history_service.get_history.assert_called_once_with(
            company_short_name='my_company',
            external_user_id='flibe',
            local_user_id=123
        )

    def test_post_when_ok_with_both_user_ids(self):
        """Test successful request with both user IDs"""
        mock_history = {
            'success': True,
            'history': [
                {
                    'id': 1,
                    'question': 'Test question',
                    'answer': 'Test answer',
                    'created_at': '2024-01-15T10:30:00Z'
                }
            ],
            'count': 1
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={
                                        'external_user_id': 'flibe',
                                        'local_user_id': 456
                                    })

        assert response.status_code == 200
        assert response.json == mock_history

        # Verify service was called correctly
        self.history_service.get_history.assert_called_once_with(
            company_short_name='my_company',
            external_user_id='flibe',
            local_user_id=456
        )

    def test_post_with_empty_history(self):
        """Test when service returns empty history"""
        mock_history = {
            'success': True,
            'history': [],
            'count': 0
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 200
        assert response.json == mock_history
        assert response.json['count'] == 0

    def test_post_with_large_history(self):
        """Test with large history response"""
        mock_history = {
            'success': True,
            'history': [
                {
                    'id': i,
                    'question': f'Question {i}',
                    'answer': f'Answer {i}',
                    'created_at': '2024-01-15T10:30:00Z'
                } for i in range(1, 11)
            ],
            'count': 10
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 200
        assert response.json == mock_history
        assert response.json['count'] == 10
        assert len(response.json['history']) == 10

    @patch("views.history_view.render_template")
    def test_post_exception_with_local_user_id(self, mock_render_template):
        """Test exception handling when local_user_id is present"""
        mock_render_template.return_value = "<html><body>Error</body></html>"
        self.history_service.get_history.side_effect = Exception('Service error')

        response = self.client.post('/my_company/history',
                                    json={
                                        'external_user_id': 'flibe',
                                        'local_user_id': 123
                                    })

        assert response.status_code == 500
        mock_render_template.assert_called_once_with(
            "error.html",
            message="Ha ocurrido un error inesperado."
        )

    def test_post_exception_without_local_user_id(self):
        """Test exception handling when local_user_id is not present"""
        self.history_service.get_history.side_effect = Exception('Service error')

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 500
        assert response.json["error_message"] == 'Service error'

    def test_post_authentication_verification_called(self):
        """Test that authentication verification is called correctly"""
        mock_history = {
            'success': True,
            'history': [],
            'count': 0
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={'external_user_id': 'test_user'})

        assert response.status_code == 200

        # Verify authentication was called correctly
        self.iauthentication.verify.assert_called_once_with('my_company', 'test_user')

    def test_post_different_company(self):
        """Test with different company short name"""
        mock_history = {
            'success': True,
            'history': [],
            'count': 0
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/test_company/history',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 200

        # Verify service was called with correct company
        self.history_service.get_history.assert_called_once_with(
            company_short_name='test_company',
            external_user_id='flibe',
            local_user_id=0
        )

    def test_post_with_additional_fields_ignored(self):
        """Test that additional fields in JSON are ignored"""
        mock_history = {
            'success': True,
            'history': [],
            'count': 0
        }

        self.history_service.get_history.return_value = mock_history

        response = self.client.post('/my_company/history',
                                    json={
                                        'external_user_id': 'flibe',
                                        'local_user_id': 123,
                                        'extra_field': 'should_be_ignored',
                                        'another_field': 456
                                    })

        assert response.status_code == 200

        # Verify only expected fields are passed to service
        self.history_service.get_history.assert_called_once_with(
            company_short_name='my_company',
            external_user_id='flibe',
            local_user_id=123
        )