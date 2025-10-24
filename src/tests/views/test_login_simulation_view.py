import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
import os
import json

from iatoolkit.views.login_simulation_view import LoginSimulationView


class TestLoginSimulationView:
    @staticmethod
    def create_app():
        """Configura una aplicación Flask mínima para las pruebas."""
        app = Flask(__name__)
        app.testing = True
        # Registramos la vista con su nueva ruta y sin inyecciones, ya que no las necesita.
        app.add_url_rule(
            '/login_test/<company_short_name>/<external_user_id>',
            view_func=LoginSimulationView.as_view('login_test')
        )
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente de pruebas antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()

    @patch("iatoolkit.views.login_simulation_view.requests.post")
    @patch.dict(os.environ, {"IATOOLKIT_API_KEY": "test-api-key"})
    def test_get_simulates_server_to_server_call_and_proxies_response(self, mock_requests_post):
        """
        Prueba que la vista LoginTest simule la llamada S2S, envíe los datos correctos,
        y reenvíe la respuesta (incluyendo cookies) al cliente final.
        """
        # 1. Configurar el Mock de la respuesta interna de 'requests.post'
        # Esta es la respuesta que nuestra vista recibirá.
        mock_internal_response = MagicMock()
        mock_internal_response.status_code = 200
        mock_internal_response.headers = {
            'Content-Type': 'text/html; charset=utf-8',
            'Set-Cookie': 'session=test-session-cookie; Path=/; HttpOnly'
        }
        # iter_content debe devolver un iterable (como una lista de bytes)
        mock_internal_response.iter_content.return_value = [b'<html><body>Success</body></html>']
        # raise_for_status no debe hacer nada si el status es 200
        mock_internal_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_internal_response

        # 2. Ejecutar la petición a nuestra vista de prueba
        company = "acme"
        user = "test-user"
        response = self.client.get(f'/login_test/{company}/{user}')

        # 3. Verificar la respuesta final que recibe el navegador
        assert response.status_code == 200
        assert response.data == b'<html><body>Success</body></html>'
        # La aserción más importante: la cookie debe haber sido reenviada
        assert 'Set-Cookie' in response.headers
        assert response.headers['Set-Cookie'] == 'session=test-session-cookie; Path=/; HttpOnly'

        # 4. Verificar que 'requests.post' fue llamado correctamente
        expected_url = f'http://localhost/{company}/external_login'
        expected_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-api-key'
        }
        expected_payload = {'external_user_id': user}

        mock_requests_post.assert_called_once_with(
            expected_url,
            headers=expected_headers,
            data=json.dumps(expected_payload),
            timeout=120,
            stream=True
        )
