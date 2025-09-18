# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import logging
import os

from flask import current_app, jsonify, send_from_directory
from flask.views import MethodView
from injector import inject

from common.auth import IAuthentication
from services.excel_service import ExcelService
from services.profile_service import ProfileService


class DownloadFileView(MethodView):
    @inject
    def __init__(self, iauthentication: IAuthentication, profile_service: ProfileService, excel_service: ExcelService):
        self.iauthentication = iauthentication
        self.profile_service = profile_service
        self.excel_service = excel_service

    def get(self, company_short_name: str, external_user_id: str, filename: str):
        if not external_user_id:
            return jsonify({"error": "Falta external_user_id"}), 400

        iauth = self.iauthentication.verify(
            company_short_name,
            body_external_user_id=external_user_id
        )
        if not iauth.get("success"):
            return jsonify(iauth), 401

        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return jsonify({"error": "Empresa no encontrada"}), 404

        file_validation = self.excel_service.validate_file_access(filename)
        if file_validation:
            return file_validation

        temp_dir = os.path.join(current_app.root_path, 'static', 'temp')

        try:
            response = send_from_directory(
                temp_dir,
                filename,
                as_attachment=True,
                mimetype='application/octet-stream'
            )
            logging.info(f"Archivo descargado via API: {filename}")
            return response
        except Exception as e:
            logging.error(f"Error descargando archivo {filename}: {str(e)}")
            return jsonify({"error": "Error descargando archivo"}), 500

