# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask.views import MethodView
from flask import render_template
from services.profile_service import ProfileService
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from injector import inject
import os


class VerifyAccountView(MethodView):
    @inject
    def __init__(self, profile_service: ProfileService):
        self.profile_service = profile_service
        self.serializer = URLSafeTimedSerializer(os.getenv("USER_VERIF_KEY"))

    def get(self, company_short_name: str, token: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        try:
            # decode the token from the URL
            email = self.serializer.loads(token, salt='email-confirm', max_age=3600*5)
        except SignatureExpired:
            return render_template('signup.html',
                                   company=company,
                                   company_short_name=company_short_name,
                                   token=token,
                                   alert_message="El enlace de verificación ha expirado. Por favor, solicita uno nuevo."), 400

        try:
            response = self.profile_service.verify_account(email)
            if "error" in response:
                return render_template(
                    'signup.html',
                    company=company,
                    company_short_name=company_short_name,
                    token=token,
                    alert_message=response["error"]), 400

            return render_template('login.html',
                                   company=company,
                                   company_short_name=company_short_name,
                                   alert_icon='success',
                                   alert_message=response['message'])
        except Exception as e:
            return render_template("error.html",
                                   company=company,
                                   company_short_name=company_short_name,
                                   message="Ha ocurrido un error inesperado."), 500
