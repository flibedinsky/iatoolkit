# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask import request, jsonify, render_template
from flask.views import MethodView
from iatoolkit.services.history_service import HistoryService
from iatoolkit.services.auth_service import AuthService
from injector import inject
import logging


class HistoryView(MethodView):
    @inject
    def __init__(self,
                 iauthentication: AuthService,
                 history_service: HistoryService ):
        self.iauthentication = iauthentication
        self.history_service = history_service

    def post(self, company_short_name):
        try:
            data = request.get_json()
        except Exception:
            return jsonify({"error_message": "Cuerpo de la solicitud JSON inválido o faltante"}), 400

        if not data:
            return jsonify({"error_message": "Cuerpo de la solicitud JSON inválido o faltante"}), 400

        # get access credentials
        iaut = self.iauthentication.verify()
        if not iaut.get("success"):
            return jsonify(iaut), 401

        external_user_id = data.get("external_user_id")
        local_user_id = iaut.get("local_user_id", 0)

        try:
            response = self.history_service.get_history(
                company_short_name=company_short_name,
                external_user_id=external_user_id,
                local_user_id=local_user_id
            )

            if "error" in response:
                return {'error_message': response["error"]}, 402

            return response, 200
        except Exception as e:
            logging.exception(
                f"Error inesperado al obtener el historial de consultas para company {company_short_name}: {e}")
            if local_user_id:
                return render_template("error.html",
                                       message="Ha ocurrido un error inesperado."), 500
            else:
                return jsonify({"error_message": str(e)}), 500
