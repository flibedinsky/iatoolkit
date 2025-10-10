# tests/services/test_branding_service.py
import pytest
from unittest.mock import Mock
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.repositories.models import Company


class TestBrandingService:

    @pytest.fixture(autouse=True)
    def setup(self):
        """
        Fixture de Pytest que se ejecuta automáticamente para cada método de test.
        Crea una instancia del servicio y almacena los valores por defecto para fácil acceso.
        """
        self.branding_service = BrandingService()
        self.default_styles = self.branding_service._default_branding

    def test_get_branding_with_no_company(self):
        """
        Prueba que se retornen los estilos por defecto y el nombre 'IAToolkit' cuando company es None.
        """
        # Act
        branding = self.branding_service.get_company_branding(None)

        # Assert
        assert branding['name'] == "IAToolkit"

        expected_header_style = (
            f"background-color: {self.default_styles['header_background_color']}; "
            f"color: {self.default_styles['header_text_color']};"
        )
        expected_company_name_style = (
            f"font-weight: {self.default_styles['company_name_font_weight']}; "
            f"font-size: {self.default_styles['company_name_font_size']};"
        )

        assert branding['header_style'] == expected_header_style
        assert branding['company_name_style'] == expected_company_name_style

    def test_get_branding_with_company_and_no_custom_branding(self):
        """
        Prueba que se retornen los estilos por defecto cuando la compañía no tiene branding personalizado.
        """
        # Arrange
        mock_company = Mock(spec=Company)
        mock_company.name = "Test Corp"
        mock_company.branding = {}

        # Act
        branding = self.branding_service.get_company_branding(mock_company)

        # Assert
        assert branding['name'] == "Test Corp"
        expected_header_style = (
            f"background-color: {self.default_styles['header_background_color']}; "
            f"color: {self.default_styles['header_text_color']};"
        )
        assert branding['header_style'] == expected_header_style

    def test_get_branding_with_partial_custom_branding(self):
        """
        Prueba que los estilos personalizados se fusionen correctamente con los por defecto.
        """
        # Arrange
        custom_styles = {
            "header_background_color": "#123456",
            "company_name_font_size": "1.5rem"
        }
        mock_company = Mock(spec=Company)
        mock_company.name = "Partial Brand Inc."
        mock_company.branding = custom_styles

        # Act
        branding = self.branding_service.get_company_branding(mock_company)

        # Assert
        assert branding['name'] == "Partial Brand Inc."

        # El color de fondo debe ser el personalizado, pero el de texto debe ser el por defecto
        expected_header_style = (
            f"background-color: #123456; "
            f"color: {self.default_styles['header_text_color']};"
        )
        assert branding['header_style'] == expected_header_style

        # El tamaño de fuente debe ser el personalizado, pero el peso debe ser el por defecto
        expected_company_name_style = (
            f"font-weight: {self.default_styles['company_name_font_weight']}; "
            f"font-size: 1.5rem;"
        )
        assert branding['company_name_style'] == expected_company_name_style

    def test_get_branding_with_full_custom_branding(self):
        """
        Prueba que todos los estilos por defecto puedan ser sobreescritos.
        """
        # Arrange
        full_custom_styles = {
            "header_background_color": "#000000",
            "header_text_color": "#FFFFFF",
            "company_name_font_weight": "normal",
            "company_name_font_size": "0.8rem"
        }
        mock_company = Mock(spec=Company)
        mock_company.name = "Full Brand LLC"
        mock_company.branding = full_custom_styles

        # Act
        branding = self.branding_service.get_company_branding(mock_company)

        # Assert
        assert branding['name'] == "Full Brand LLC"

        expected_header_style = "background-color: #000000; color: #FFFFFF;"
        expected_company_name_style = "font-weight: normal; font-size: 0.8rem;"

        assert branding['header_style'] == expected_header_style
        assert branding['company_name_style'] == expected_company_name_style
