# src/tests/views/test_home_view.py

import pytest
from flask import Flask
from unittest.mock import MagicMock, patch

from iatoolkit.repositories.models import Company
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.views.home_view import HomeView


class TestHomeView:
    @staticmethod
    def create_app():
        """Configura la aplicación Flask para pruebas."""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.testing = True
        return app

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configura el cliente y los mocks antes de cada test."""
        self.app = self.create_app()
        self.client = self.app.test_client()
        self.profile_service = MagicMock(spec=ProfileService)
        self.branding_service = MagicMock(spec=BrandingService)

        self.test_company = Company(id=1, name="Test Co", short_name="test_co")
        self.profile_service.get_company_by_short_name.return_value = self.test_company
        self.branding_service.get_company_branding.return_value = {"name": "Test Co Branding"}

        # Registrar la vista principal
        view = HomeView.as_view("home",
                                profile_service=self.profile_service,
                                branding_service=self.branding_service)
        self.app.add_url_rule("/<string:company_short_name>/home.html", view_func=view, methods=["GET"])

        # Añadir rutas dummy para que los url_for() del template _login_widget.html no fallen
        @self.app.route("/<string:company_short_name>/login", endpoint="login", methods=["POST"])
        def dummy_login(company_short_name):
            return "Login Page", 200

        @self.app.route("/<string:company_short_name>/signup", endpoint="signup")
        def dummy_signup(company_short_name):
            return "Signup Page", 200

        @self.app.route("/<string:company_short_name>/forgot_password", endpoint="forgot_password")
        def dummy_forgot_password(company_short_name):
            return "Forgot Password Page", 200

    @patch("iatoolkit.views.home_view.render_template")
    def test_get_home_page_success(self, mock_render_template):
        """Prueba que la página de inicio se carga correctamente sin alertas en la sesión."""
        mock_render_template.return_value = "<html></html>"

        response = self.client.get("/test_co/home.html")

        assert response.status_code == 200
        mock_render_template.assert_called_once_with(
            'home.html',
            company=self.test_company,
            company_short_name='test_co',
            branding=self.branding_service.get_company_branding.return_value,
            alert_message=None,
            alert_icon='error'  # 'error' es el valor por defecto de session.pop
        )

    @patch("iatoolkit.views.home_view.render_template")
    def test_get_home_page_with_session_alerts(self, mock_render_template):
        """Prueba que la vista procesa y limpia correctamente las alertas de la sesión."""
        mock_render_template.return_value = "<html></html>"
        success_message = "¡Acción completada con éxito!"

        # Preparar la sesión con los datos de la alerta
        with self.client.session_transaction() as sess:
            sess['alert_message'] = success_message
            sess['alert_icon'] = 'success'

        response = self.client.get("/test_co/home.html")

        # Afirmar que se renderizó con los datos de la sesión
        assert response.status_code == 200
        mock_render_template.assert_called_once_with(
            'home.html',
            company=self.test_company,
            company_short_name='test_co',
            branding=self.branding_service.get_company_branding.return_value,
            alert_message=success_message,
            alert_icon='success'
        )

        with self.client.session_transaction() as sess:
            assert 'alert_message' not in sess
            assert 'alert_icon' not in sess

    def test_get_home_page_invalid_company(self):
        """Prueba que se devuelve un 404 si la empresa no es válida."""
        self.profile_service.get_company_by_short_name.return_value = None

        response = self.client.get("/invalid_co/home.html")

        assert response.status_code == 404
        # Verificamos el texto con el caracter de comilla simple escapado (&#39;)
        # ya que Flask lo convierte automáticamente en su página de error por defecto.
        assert b"La empresa &#39;invalid_co&#39; no fue encontrada." in response.data