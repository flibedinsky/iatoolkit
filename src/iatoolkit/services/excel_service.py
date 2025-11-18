# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.common.util import Utility
import pandas as pd
from uuid import uuid4
from pathlib import Path
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.services.i18n_service import I18nService
from injector import inject
import os
import logging
from flask import current_app, jsonify

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExcelService:
    @inject
    def __init__(self,
                 util: Utility,
                 i18n_service: I18nService):
        self.util = util
        self.i18n_service = i18n_service

    def excel_generator(self, company_short_name: str, **kwargs) -> str:
        """
        Genera un Excel a partir de una lista de diccionarios.

        Parámetros esperados en kwargs:
          - filename: str (nombre lógico a mostrar, ej. "reporte_clientes.xlsx") [obligatorio]
          - data: list[dict] (filas del excel) [obligatorio]
          - sheet_name: str = "hoja 1"

        Retorna:
             {
                "filename": "reporte.xlsx",
                "attachment_token": "8b7f8a66-...-c1c3.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "download_link": "/download/8b7f8a66-...-c1c3.xlsx"
                }
        """
        try:
            # get the parameters
            fname = kwargs.get('filename')
            if not fname:
                return self.i18n_service.t('errors.services.no_output_file')

            data = kwargs.get('data')
            if not data or not isinstance(data, list):
                return self.i18n_service.t('errors.services.no_data_for_excel')

            sheet_name = kwargs.get('sheet_name', 'hoja 1')

            # 1. convert dictionary to dataframe
            df = pd.DataFrame(data)

            # 3. create temporary name
            token = f"{uuid4()}.xlsx"

            # 4. check that download directory is configured
            if 'IATOOLKIT_DOWNLOAD_DIR' not in current_app.config:
                return self.i18n_service.t('errors.services.no_download_directory')

            download_dir = current_app.config['IATOOLKIT_DOWNLOAD_DIR']
            filepath = Path(download_dir) / token
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # 4. save excel file in temporary directory
            df.to_excel(filepath, index=False, sheet_name=sheet_name)

            # 5. return the  link to the LLM
            return {
                "filename": fname,
                "attachment_token": token,
                "content_type": EXCEL_MIME,
                "download_link": f"/download/{token}"
                }

        except Exception as e:
            raise IAToolkitException(IAToolkitException.ErrorType.CALL_ERROR,
                               self.i18n_service.t('errors.services.cannot_create_excel')) from e

    def validate_file_access(self, filename):
        try:
            if not filename:
                return jsonify({"error": self.i18n_service.t('errors.services.invalid_filename')})
            # Prevent path traversal attacks
            if '..' in filename or filename.startswith('/') or '\\' in filename:
                return jsonify({"error": self.i18n_service.t('errors.services.invalid_filename')})

            temp_dir = os.path.join(current_app.root_path, 'static', 'temp')
            file_path = os.path.join(temp_dir, filename)

            if not os.path.exists(file_path):
                return jsonify({"error": self.i18n_service.t('errors.services.file_not_exist')})

            if not os.path.isfile(file_path):
                return jsonify({"error": self.i18n_service.t('errors.services.path_is_not_a_file')})

            return None

        except Exception as e:
            error_msg = f"File validation error {filename}: {str(e)}"
            logging.error(error_msg)
            return jsonify({"error": self.i18n_service.t('errors.services.file_validation_error')})