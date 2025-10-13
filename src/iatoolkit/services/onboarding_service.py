# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.models import Company
from typing import List, Dict, Any


class OnboardingService:
    """
    Servicio para gestionar las tarjetas de contenido que se muestran
    durante la pantalla de carga (onboarding).
    """

    def __init__(self):
        """
        Define el conjunto de tarjetas de onboarding por defecto.
        """
        self._default_cards = [
            {'icon': 'fas fa-users', 'title': 'Clientes',
             'text': 'Conozco en detalle a nuestros clientes: antigüedad, contactos, historial de operaciones.<br><br><strong>Ejemplo:</strong> ¿cuántos clientes nuevos se incorporaron a mi cartera este año?'},
            {'icon': 'fas fa-cubes', 'title': 'Productos',
             'text': 'Productos: características, condiciones, historial.'},

            {'icon': 'fas fa-cogs', 'title': 'Personaliza tus Prompts',
             'text': 'Utiliza la varita mágica y podrás explorar los prompts predefinidos que he preparado para ti.'},
            {'icon': 'fas fa-table', 'title': 'Tablas y Excel',
             'text': 'Puedes pedirme la respuesta en formato de tablas o excel.<br><br><strong>Ejemplo:</strong> dame una tabla con los 10 certificados más grandes este año.'},
            {'icon': 'fas fa-shield-alt', 'title': 'Seguridad y Confidencialidad',
             'text': 'Toda tu información es procesada de forma segura y confidencial dentro de nuestro entorno protegido.'}
        ]

    def get_onboarding_cards(self, company: Company | None) -> List[Dict[str, Any]]:
        """
        Retorna la lista de tarjetas de onboarding para una compañía.
        Si la compañía tiene tarjetas personalizadas, las devuelve.
        De lo contrario, devuelve las tarjetas por defecto.
        """
        if company and company.onboarding_cards:
            return company.onboarding_cards

        return self._default_cards
