# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from common.util import Utility
import pandas as pd
from uuid import uuid4
from pathlib import Path
from common.exceptions import AppException
from injector import inject
import os
import logging
from flask import current_app, jsonify

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExcelService:
    @inject
    def __init__(self,util: Utility):
        self.util = util

    def excel_generator(self, **kwargs) -> str:
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
                return 'falta el nombre del archivo de salida'

            data = kwargs.get('data')
            if not data or not isinstance(data, list):
                return 'faltan los datos  o no es una lista de diccionarios'

            sheet_name = kwargs.get('sheet_name', 'hoja 1')

            # 1. convert dictionary to dataframe
            df = pd.DataFrame(data)

            # 3. create temporary name
            token = f"{uuid4()}.xlsx"
            filepath = Path("static/temp") / token
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
            raise AppException(AppException.ErrorType.CALL_ERROR,
                               'error generating excel file') from e

    def validate_file_access(self, filename):
        try:
            if not filename:
                return jsonify({"error": "Nombre de archivo inválido"})
            # Prevent path traversal attacks
            if '..' in filename or filename.startswith('/') or '\\' in filename:
                return jsonify({"error": "Nombre de archivo inválido"})

            temp_dir = os.path.join(current_app.root_path, 'static', 'temp')
            file_path = os.path.join(temp_dir, filename)

            if not os.path.exists(file_path):
                return jsonify({"error": "Archivo no encontrado"})

            if not os.path.isfile(file_path):
                return jsonify({"error": "La ruta no corresponde a un archivo"})

            return None

        except Exception as e:
            error_msg = f"Error validando acceso al archivo {filename}: {str(e)}"
            logging.error(error_msg)
            return jsonify({"error": "Error validando archivo"})