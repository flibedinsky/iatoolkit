# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from infra.call_service import CallServiceClient
from injector import inject
from common.exceptions import AppException
import json


class ApiService:
    @inject
    def __init__(self, call_service: CallServiceClient):
        self.call_service = call_service

    def call_api(self, endpoint: str, method: str, **kwargs):
        if method == 'get':
            response, status_code = self.call_service.get(endpoint)
        elif method == 'post':
            response, status_code = self.call_service.post(endpoint=endpoint, json_dict=kwargs)
        else:
            raise AppException(AppException.ErrorType.INVALID_PARAMETER,
                               f'API error, {method} not supported')

        if status_code != 200:
            raise AppException(AppException.ErrorType.CALL_ERROR,
                               f'API {endpoint} error: {status_code}')

        return json.dumps(response)
