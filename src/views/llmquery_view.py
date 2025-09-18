# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import request, jsonify, render_template
from flask.views import MethodView
from services.query_service import QueryService
from common.auth import IAuthentication
from injector import inject
import logging


class LLMQueryView(MethodView):
    @inject
    def __init__(self,
                 iauthentication: IAuthentication,
                 query_service: QueryService,
                 ):
        self.iauthentication = iauthentication
        self.query_service = query_service

    def post(self, company_short_name):
        data = request.get_json()
        if not data:
            return jsonify({"error_message": "Cuerpo de la solicitud JSON inválido o faltante"}), 400

        # get access credentials
        iaut = self.iauthentication.verify(company_short_name, data.get("external_user_id"))
        if not iaut.get("success"):
            return jsonify(iaut), 401

        company_id = iaut.get("company_id")
        external_user_id = iaut.get("external_user_id")
        local_user_id = iaut.get("local_user_id")

        # now check the form
        question = data.get("question")
        files = data.get("files", [])
        client_data = data.get("client_data", {})
        prompt_name = data.get("prompt_name")
        if not question and not prompt_name:
            return jsonify({"error_message": "Falta la consulta o el prompt_name"}), 400

        try:
            response = self.query_service.llm_query(
                company_short_name=company_short_name,
                external_user_id=external_user_id,
                local_user_id=local_user_id,
                question=question,
                prompt_name=prompt_name,
                client_data=client_data,
                files=files)
            if "error" in response:
                return {'error_message': response.get("error_message", '')}, 401

            return response, 200
        except Exception as e:
            logging.exception(
                f"Error inesperado al procesar llm_query para company {company_short_name}: {e}")
            if local_user_id:
                return render_template("error.html",
                                       message="Ha ocurrido un error inesperado."), 500
            else:
                return jsonify({"error_message": str(e)}), 500
