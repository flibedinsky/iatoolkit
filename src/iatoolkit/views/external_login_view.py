# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import os
import logging
from flask import request, jsonify
from flask.views import MethodView
from injector import inject
from iatoolkit.services.auth_service import AuthService
from iatoolkit.views.base_login_view import BaseLoginView

# Importar los servicios que necesita la clase base
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.jwt_service import JWTService
from iatoolkit.services.branding_service import BrandingService
from iatoolkit.services.onboarding_service import OnboardingService
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.prompt_manager_service import PromptService

class ExternalLoginView(BaseLoginView):
    """
    Handles login for external users via API.
    Authenticates and then delegates the path decision (fast/slow) to the base class.
    """
    @inject
    def __init__(self,
                 iauthentication: AuthService,
                 jwt_service: JWTService,
                 profile_service: ProfileService,
                 branding_service: BrandingService,
                 prompt_service: PromptService,
                 onboarding_service: OnboardingService,
                 query_service: QueryService):
        # Pass the dependencies for the base class to its __init__
        super().__init__(
            profile_service=profile_service,
            jwt_service=jwt_service,
            branding_service=branding_service,
            onboarding_service=onboarding_service,
            query_service=query_service,
            prompt_service=prompt_service,
        )
        # Handle the dependency specific to this child class
        self.iauthentication = iauthentication

    def post(self, company_short_name: str):
        data = request.get_json()
        if not data or 'user_identifier' not in data:
            return jsonify({"error": "Falta user_identifier"}), 400

        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return jsonify({"error": "Empresa no encontrada"}), 404

        user_identifier = data.get('user_identifier')
        if not user_identifier:
            return jsonify({"error": "missing user_identifier"}), 404

        # 1. Authenticate the API call.
        iaut = self.iauthentication.verify()
        if not iaut.get("success"):
            return jsonify(iaut), 401

        # 2. Create the external user session.
        self.profile_service.create_external_user_session(company, user_identifier)

        # 3. Delegate the path decision to the centralized logic.
        try:
            return self._handle_login_path(company_short_name, user_identifier, company)
        except Exception as e:
            logging.exception(f"Error processing external login path for {company_short_name}/{user_identifier}: {e}")
            return jsonify({"error": f"Internal server error while starting chat. {str(e)}"}), 500


class RedeemTokenApiView(MethodView):
    # this endpoint is only used ONLY by chat_main.js to redeem a chat token
    @inject
    def __init__(self,
                 profile_service: ProfileService,
                 jwt_service: JWTService):
        self.profile_service = profile_service
        self.jwt_service = jwt_service

    def post(self, company_short_name: str):
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({"error": "Falta token de validación"}), 400

        # 1. validate the token
        token = data.get('token')
        payload = self.jwt_service.validate_chat_jwt(token)
        if not payload:
            logging.warning("Intento de canjear un token inválido o expirado.")
            return {"error": "Token inválido o expirado."}, 401

        # 2. if token is valid, extract the user_identifier
        user_identifier = payload.get('user_identifier')

        try:
            # 3. create the Flask session
            self.profile_service.set_session_for_user(company_short_name, user_identifier)
            logging.info(f"Token de sesión canjeado exitosamente para {user_identifier}.")

            return {"status": "ok"}, 200

        except Exception as e:
            logging.error(f"Error al crear la sesión desde token para {user_identifier}: {e}")
            return {"error": "No se pudo crear la sesión del usuario."}, 500