# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask.views import MethodView
from flask import request, jsonify
from services.load_documents_service import LoadDocumentsService
from repositories.profile_repo import ProfileRepo
from injector import inject
import base64


class FileStoreView(MethodView):
    @inject
    def __init__(self,
                 doc_service: LoadDocumentsService,
                 profile_repo: ProfileRepo,):
        self.doc_service = doc_service
        self.profile_repo = profile_repo

    def post(self):
        try:
            req_data = request.get_json()

            required_fields = ['company', 'filename', 'content']
            for field in required_fields:
                if field not in req_data:
                    return jsonify({"error": f"El campo {field} es requerido"}), 400

            company_short_name = req_data.get('company', '')
            filename = req_data.get('filename', False)
            base64_content = req_data.get('content', '')
            metadata = req_data.get('metadata', {})

            # get company
            company = self.profile_repo.get_company_by_short_name(company_short_name)
            if not company:
                return jsonify({"error": f"La empresa {company_short_name} no existe"}), 400

            # get the file content from base64
            content = base64.b64decode(base64_content)

            new_document = self.doc_service.load_file(
                filename=filename,
                content=content,
                company=company,
                metadata=metadata)

            return jsonify({
                "document_id": new_document.id,
            }), 200

        except Exception as e:
            response = jsonify({"error": str(e)})
            response.status_code = 500

            return response
