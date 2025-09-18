# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask.views import MethodView
from flask import render_template, request, redirect, flash, url_for
from src.services.profile_service import ProfileService
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from flask_bcrypt import Bcrypt
from injector import inject
import os


class ChangePasswordView(MethodView):
    @inject
    def __init__(self, profile_service: ProfileService):
        self.profile_service = profile_service

        self.serializer = URLSafeTimedSerializer(os.getenv("PASS_RESET_KEY"))
        self.bcrypt = Bcrypt()

    def get(self, company_short_name: str, token: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message=f"Empresa no encontrada: {company_short_name}"), 404

        try:
            # Decodificar el token
            email = self.serializer.loads(token, salt='password-reset', max_age=3600)
        except SignatureExpired as e:
            return render_template('forgot_password.html',
                        alert_message="El enlace de cambio de contraseña ha expirado. Por favor, solicita uno nuevo.")

        return render_template('change_password.html',
                               company_short_name=company_short_name,
                               company=company,
                               token=token, email=email)

    def post(self, company_short_name: str, token: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message=f"Empresa no encontrada: {company_short_name}"), 404

        try:
            # Decodificar el token
            email = self.serializer.loads(token, salt='password-reset', max_age=3600)
        except SignatureExpired:
            return render_template('forgot_password.html',
                                   company_short_name=company_short_name,
                                   company=company,
                                    alert_message="El enlace de cambio de contraseña ha expirado. Por favor, solicita uno nuevo.")

        try:
            # Obtener datos del formulario
            temp_code = request.form.get('temp_code')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            response = self.profile_service.change_password(
                email=email,
                temp_code=temp_code,
                new_password=new_password,
                confirm_password=confirm_password
            )

            if "error" in response:
                return render_template(
                    'change_password.html',
                    token=token,
                    company_short_name=company_short_name,
                    company=company,
                    form_data={"temp_code": temp_code,
                               "new_password": new_password,
                               "confirm_password": confirm_password},
                    alert_message=response["error"]), 400


            return render_template('login.html',
                                   company_short_name=company_short_name,
                                   company=company,
                                   alert_icon='success',
                               alert_message="Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión.")

        except Exception as e:
            return render_template("error.html",
                                   company=company,
                                   company_short_name=company_short_name,
                                   message="Ha ocurrido un error inesperado."), 500
