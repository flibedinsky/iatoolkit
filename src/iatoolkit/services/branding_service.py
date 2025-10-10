# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.models import Company


class BrandingService:
    """
    Servicio centralizado que gestiona la configuración de branding.
    """

    def __init__(self):
        """
        Define los estilos de branding por defecto para la aplicación.
        """
        self._default_branding = {
            # Colores del contenedor del encabezado
            "header_background_color": "#FFFFFF",  # Fondo blanco por defecto
            "header_text_color": "#6C757D",  # Color de texto 'muted' de Bootstrap

            # Estilos para el nombre de la compañía
            "company_name_font_weight": "bold",  # Nombre en negrita por defecto
            "company_name_font_size": "1rem",  # Tamaño de fuente estándar
        }

    def get_company_branding(self, company: Company | None) -> dict:
        """
        Retorna los estilos de branding finales para una compañía,
        fusionando los valores por defecto con los personalizados.

        Args:
            company: El objeto Company, que puede contener un dict de branding.

        Returns:
            Un diccionario con todos los estilos de branding listos para usar en la plantilla.
        """
        # Empezamos con una copia de los valores por defecto
        final_branding_values = self._default_branding.copy()

        # Si la compañía existe y tiene branding personalizado, lo fusionamos.
        if company and company.branding:
            final_branding_values.update(company.branding)

        # Construimos las cadenas de estilo completas
        header_style = (
            f"background-color: {final_branding_values['header_background_color']}; "
            f"color: {final_branding_values['header_text_color']};"
        )
        company_name_style = (
            f"font-weight: {final_branding_values['company_name_font_weight']}; "
            f"font-size: {final_branding_values['company_name_font_size']};"
        )

        return {
            "name": company.name if company else "IAToolkit",
            "header_style": header_style,
            "company_name_style": company_name_style
        }