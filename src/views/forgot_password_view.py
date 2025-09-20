# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask.views import MethodView
from flask import render_template, request, url_for
from injector import inject
from services.profile_service import ProfileService
from itsdangerous import URLSafeTimedSerializer
import os

class ForgotPasswordView(MethodView):
    @inject
    def __init__(self, profile_service: ProfileService):
        self.profile_service = profile_service
        self.serializer = URLSafeTimedSerializer(os.getenv("PASS_RESET_KEY"))

    def get(self, company_short_name: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        return render_template('forgot_password.html',
                               company=company,
                               company_short_name=company_short_name
                               )

    def post(self, company_short_name: str):
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        try:
            email = request.form.get('email')

            # create a safe token and url for it
            token = self.serializer.dumps(email, salt='password-reset')
            reset_url = url_for('change_password',
                                company_short_name=company_short_name,
                                token=token, _external=True)

            response = self.profile_service.forgot_password(email=email, reset_url=reset_url)
            if "error" in response:
                return render_template(
                    'forgot_password.html',
                    company=company,
                    company_short_name=company_short_name,
                    form_data={"email": email },
                    alert_message=response["error"]), 400


            return render_template('login.html',
                                   company=company,
                                   company_short_name=company_short_name,
                                   alert_icon='success',
                                   alert_message="Hemos enviado un enlace a tu correo para restablecer la contraseña.")
        except Exception as e:
            return render_template("error.html",
                                   company=company,
                                   company_short_name=company_short_name,
                                   message="Ha ocurrido un error inesperado."), 500

