# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from views.user_feedback_view import UserFeedbackView
from services.user_feedback_service import UserFeedbackService
from common.auth import IAuthentication


class TestUserFeedbackView:
    @staticmethod
    def create_app():
        app = Flask(__name__)
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.feedback_service = MagicMock(spec=UserFeedbackService)
        self.iauthentication = MagicMock(spec=IAuthentication)

        self.iauthentication.verify.return_value = {
            'success': True,
            'company_id': 101,
            'external_user_id': 'test_user_id'
        }

        # register the view
        self.feedback_view = UserFeedbackView.as_view("feedback",
                                          user_feedback_service=self.feedback_service,
                                            iauthentication=self.iauthentication)
        self.app.add_url_rule('/<company_short_name>/feedback',
                              view_func=self.feedback_view,
                              methods=["POST"])


    def test_post_when_missing_data(self):
        response = self.client.post('/maxxa/feedback',
                                    json={})

        assert response.status_code == 400
        self.feedback_service.new_feedback.assert_not_called()

    def test_post_when_auth_error(self):
        self.iauthentication.verify.return_value = {'error_message': 'error in authentication'}
        response = self.client.post('/maxxa/feedback',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 401
        assert response.json["error_message"] == 'error in authentication'

    def test_post_when_missing_message(self):
        response = self.client.post('/maxxa/feedback',
                                    json={'external_user_id': 'flibe'})

        assert response.status_code == 400
        assert response.json["error_message"] == 'Falta el mensaje de feedback'
        self.feedback_service.new_feedback.assert_not_called()

    def test_post_when_missing_space(self):
        response = self.client.post('/maxxa/feedback',
                                    json={'external_user_id': 'flibe', 'message': 'test message'})

        assert response.status_code == 400
        assert response.json["error_message"] == 'Falta el espacio de Google Chat'
        self.feedback_service.new_feedback.assert_not_called()

    def test_post_when_missing_type(self):
        response = self.client.post('/maxxa/feedback',
                                    json={'external_user_id': 'flibe', 'message': 'test message', 'space': 'spaces/test'})

        assert response.status_code == 400
        assert response.json["error_message"] == 'Falta el tipo de feedback'
        self.feedback_service.new_feedback.assert_not_called()

    def test_post_when_missing_rating(self):
        response = self.client.post('/maxxa/feedback',
                                    json={'external_user_id': 'flibe', 'message': 'test message', 'space': 'spaces/test', 'type': 'MESSAGE_TRIGGER'})

        assert response.status_code == 400
        assert response.json["error_message"] == 'Falta la calificación'
        self.feedback_service.new_feedback.assert_not_called()

    @patch("views.user_feedback_view.render_template")
    def test_post_when_exception(self, mock_render_template):
        mock_render_template.return_value = "<html><body></body></html>"
        self.feedback_service.new_feedback.side_effect = Exception('error')

        response = self.client.post('/maxxa/feedback',
                                    json={
                                        'message': 'feedback message', 
                                        'external_user_id': 'flibe',
                                        'space': 'spaces/test',
                                        'type': 'MESSAGE_TRIGGER',
                                        'rating': 4
                                    })

        assert response.status_code == 500

    def test_post_when_service_error(self):
        self.feedback_service.new_feedback.return_value = {'error': 'an error'}

        response = self.client.post('/maxxa/feedback',
                                    json={
                                        'message': 'feedback message', 
                                        'external_user_id': 'flibe',
                                        'space': 'spaces/test',
                                        'type': 'MESSAGE_TRIGGER',
                                        'rating': 3
                                    })

        assert response.status_code == 402
        assert response.json == {'error_message': 'an error'}

    def test_post_when_ok(self):
        self.feedback_service.new_feedback.return_value = {'message': "Feedback guardado correctamente"}

        response = self.client.post('/maxxa/feedback',
                                    json={
                                        'message': 'feedback message', 
                                        'external_user_id': 'flibe',
                                        'space': 'spaces/test',
                                        'type': 'MESSAGE_TRIGGER',
                                        'rating': 5
                                    })

        assert response.status_code == 200
        assert response.json == {'message': "Feedback guardado correctamente"}

    def test_post_with_all_required_fields(self):
        """Test that all required fields are passed to the service correctly"""
        self.feedback_service.new_feedback.return_value = {'message': "Feedback guardado correctamente"}

        test_data = {
            'message': 'test feedback message',
            'external_user_id': 'test_user_123',
            'local_user_id': 456,
            'space': 'spaces/custom-space',
            'type': 'CUSTOM_TYPE',
            'rating': 4
        }

        response = self.client.post('/maxxa/feedback', json=test_data)

        assert response.status_code == 200

        # Verify service was called with all parameters
        self.feedback_service.new_feedback.assert_called_once_with(
            company_short_name='maxxa',
            message='test feedback message',
            external_user_id='test_user_123',
            local_user_id=456,
            space='spaces/custom-space',
            type='CUSTOM_TYPE',
            rating=4
        )

    def test_post_with_optional_local_user_id(self):
        """Test that local_user_id is optional and defaults to 0"""
        self.feedback_service.new_feedback.return_value = {'message': "Feedback guardado correctamente"}

        test_data = {
            'message': 'test feedback message',
            'external_user_id': 'test_user_123',
            'space': 'spaces/test',
            'type': 'MESSAGE_TRIGGER',
            'rating': 2
        }

        response = self.client.post('/maxxa/feedback', json=test_data)

        assert response.status_code == 200

        # Verify service was called with default local_user_id
        call_args = self.feedback_service.new_feedback.call_args[1]
        assert call_args['local_user_id'] == 0

    def test_post_with_different_rating_values(self):
        """Test that different rating values are accepted"""
        self.feedback_service.new_feedback.return_value = {'message': "Feedback guardado correctamente"}

        # Test with rating 1
        response1 = self.client.post('/maxxa/feedback',
                                    json={
                                        'message': 'feedback message', 
                                        'external_user_id': 'flibe',
                                        'space': 'spaces/test',
                                        'type': 'MESSAGE_TRIGGER',
                                        'rating': 1
                                    })
        assert response1.status_code == 200

        # Test with rating 5
        response2 = self.client.post('/maxxa/feedback',
                                    json={
                                        'message': 'feedback message', 
                                        'external_user_id': 'flibe',
                                        'space': 'spaces/test',
                                        'type': 'MESSAGE_TRIGGER',
                                        'rating': 5
                                    })
        assert response2.status_code == 200

        # Verify both calls were made with correct ratings
        calls = self.feedback_service.new_feedback.call_args_list
        assert len(calls) == 2
        assert calls[0][1]['rating'] == 1
        assert calls[1][1]['rating'] == 5
