# tests/services/test_onboarding_service.py
import pytest
from unittest.mock import Mock
from iatoolkit.services.onboarding_service import OnboardingService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.repositories.models import Company

class TestOnboardingService:
    """
    Pruebas para el OnboardingService que gestiona las tarjetas de la pantalla de carga.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """
        Fixture de Pytest que se ejecuta para cada test.
        Crea una instancia del servicio y almacena las tarjetas por defecto.
        """
        self.configuration_service = Mock(spec=ConfigurationService)
        self.onboarding_service = OnboardingService(self.configuration_service)
        self.default_cards = self.onboarding_service._default_cards

        self.configuration_service.get_company_content.return_value = self.default_cards


    def test_get_cards_with_no_company(self):
        """Prueba que se retornen las tarjetas por defecto cuando company es None."""
        # Act
        cards = self.onboarding_service.get_onboarding_cards(None)
        # Assert
        assert cards == self.default_cards
        assert len(cards) > 0

    def test_get_cards_with_company_and_no_custom_cards(self):
        """Prueba que se retornen las tarjetas por defecto cuando la compañía no tiene personalización."""
        # Arrange
        mock_company = Mock(spec=Company)
        # Simula una compañía sin tarjetas personalizadas (el campo estaría en None)
        mock_company.onboarding_cards = None

        # Act
        cards = self.onboarding_service.get_onboarding_cards(mock_company)

        # Assert
        assert cards == self.default_cards

    def test_get_cards_with_company_and_empty_custom_cards_list(self):
        """Prueba que se retornen las tarjetas por defecto si la lista de tarjetas personalizadas está vacía."""
        # Arrange
        mock_company = Mock(spec=Company)
        # Simula una compañía con una lista de tarjetas vacía.
        mock_company.onboarding_cards = []

        # Act
        cards = self.onboarding_service.get_onboarding_cards(mock_company)

        # Assert
        assert cards == self.default_cards

    def test_get_cards_with_company_and_custom_cards(self):
        """Prueba que las tarjetas personalizadas de la compañía se retornen correctamente."""
        # Arrange
        custom_cards = [
            {'icon': 'fas fa-rocket', 'title': 'Tarjeta Personalizada', 'text': 'Este es un contenido único.'}
        ]
        mock_company = Mock(spec=Company)
        self.configuration_service.get_company_content.return_value = custom_cards

        # Act
        cards = self.onboarding_service.get_onboarding_cards(mock_company)

        # Assert
        assert cards == custom_cards
        assert cards != self.default_cards
