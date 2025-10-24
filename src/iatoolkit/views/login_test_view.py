# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask.views import MethodView
from flask import render_template, request
from injector import inject
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.services.onboarding_service import OnboardingService
import os


class LoginTest(MethodView):
    @inject
    def __init__(self,
                 profile_service: ProfileService,
                 branding_service: BrandingService,
                 onboarding_service: OnboardingService):
        self.profile_service = profile_service
        self.branding_service = branding_service
        self.onboarding_service = onboarding_service

    def get(self):
        alert_message = request.args.get('alert_message', None)
        companies = self.profile_service.get_companies()
        branding_data = None
        onboarding_cards = {}
        if companies:
            # Obtener el branding de la primera empresa para la página de prueba
            first_company = companies[0]
            branding_data = self.branding_service.get_company_branding(first_company)
            onboarding_cards = self.onboarding_service.get_onboarding_cards(first_company)

        # Esta API_KEY para el login
        api_key_for_login = os.getenv("IATOOLKIT_API_KEY", "tu_api_key_por_defecto_o_error")

        return render_template('login_test.html',
                               companies=companies,
                               branding=branding_data,
                               onboarding_cards=onboarding_cards,
                               alert_message=alert_message,
                               alert_icon='success' if alert_message else None,
                               api_key=api_key_for_login
                               )
