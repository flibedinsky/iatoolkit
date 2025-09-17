# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import logging
import requests
from requests import RequestException
from exceptions import AppException
from injector import inject

class CallServiceClient:
    @inject
    def __init__(self):
        self.headers = {'Content-Type': 'application/json'}

    def _deserialize_response(self, response):
        try:
            return response.json(), response.status_code
        except Exception as e:
            return {'error_type': f'JSON error: {str(e)}'}, response.status_code

    def get(self, endpoint, params=None, timeout=(10, 200)):
        if params is None:
            params = {}

        if isinstance(timeout, int):
            timeout = (10, timeout)

        try:
            response = requests.get(endpoint, params=params, timeout=timeout)
        except RequestException as e:
            logging.exception(e)
            raise AppException(AppException.ErrorType.REQUEST_ERROR, f'request error: {str(e)}')
        return self._deserialize_response(response)

    def post(self, endpoint, json_dict, timeout=(10, 200)):
        if isinstance(timeout, int):
            timeout = (10, timeout)
        try:
            response = requests.post(endpoint, json=json_dict, headers=self.headers, timeout=timeout)
        except RequestException as e:
            logging.exception(e)
            raise AppException(AppException.ErrorType.REQUEST_ERROR, str(e))
        return self._deserialize_response(response)

    def put(self, endpoint, json_dict, timeout=(10, 200)):
        if isinstance(timeout, int):
            timeout = (10, timeout)
        try:
            response = requests.put(endpoint, json=json_dict, headers=self.headers, timeout=timeout)
        except RequestException as e:
            logging.exception(e)
            raise AppException(AppException.ErrorType.REQUEST_ERROR, str(e))
        return self._deserialize_response(response)

    def patch(self, endpoint, json_dict, timeout=(10, 200)):
        if isinstance(timeout, int):
            timeout = (10, timeout)
        try:
            response = requests.patch(endpoint, json=json_dict, headers=self.headers, timeout=timeout)
        except RequestException as e:
            raise AppException(AppException.ErrorType.REQUEST_ERROR, str(e))
        return self._deserialize_response(response)

    def delete(self, endpoint, json_dict, timeout=(10, 200)):
        if isinstance(timeout, int):
            timeout = (10, timeout)
        try:
            response = requests.delete(endpoint, json=json_dict, headers=self.headers, timeout=timeout)
        except RequestException as e:
            raise AppException(AppException.ErrorType.REQUEST_ERROR, str(e))
        return self._deserialize_response(response)

    def post_files(self, endpoint, data, timeout=(10, 200)):
        if isinstance(timeout, int):
            timeout = (10, timeout)
        try:
            response = requests.post(endpoint, files=data, timeout=timeout)
        except RequestException as e:
            raise AppException(AppException.ErrorType.REQUEST_ERROR, str(e))
        return self._deserialize_response(response)

