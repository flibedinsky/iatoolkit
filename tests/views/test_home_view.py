import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
import os

# Asegúrate de que las importaciones sean correctas y existan
from views.home_view import HomeView
from services.profile_service import ProfileService
from repositories.models import Company


# Ya no necesitamos JWTService, ChatTokenRequestView, etc.

class TestHomeView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y el mock antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.profile_service = MagicMock(spec=ProfileService)
        self.test_company = Company(id=1, name='a company', short_name='test_company')
        self.profile_service.get_companies.return_value = [self.test_company]

        # Registrar únicamente la vista que estamos probando.
        # No necesitamos registrar las otras vistas que han sido eliminadas.
        view = HomeView.as_view("home", profile_service=self.profile_service)
        self.app.add_url_rule("/", view_func=view, methods=["GET"])

    @patch("views.home_view.render_template")
    @patch.dict(os.environ, {"IATOOLKIT_API_KEY": "una_api_key_de_prueba_segura"})
    def test_get_home_page(self, mock_render_template):
        """
        Prueba que la página de inicio se renderice correctamente sin los parámetros obsoletos.
        """
        mock_render_template.return_value = "<html><body><h1>Home Page</h1></body></html>"

        # Ya no necesitamos el contexto de la petición para generar las URLs
        response = self.client.get("/")

        assert response.status_code == 200
        assert b"<h1>Home Page</h1>" in response.data

        # La aserción ahora debe reflejar los argumentos actuales de render_template en HomeView
        mock_render_template.assert_called_once_with(
            "home.html",
            companies=[self.test_company],
            is_mobile=False,
            alert_icon=None,
            alert_message=None,
            api_key="una_api_key_de_prueba_segura",
            # Hemos eliminado los siguientes parámetros obsoletos:
            # chat_token_request_url=...
            # public_chat_url_template=...
        )