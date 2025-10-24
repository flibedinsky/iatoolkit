import requests
import json
import os
from flask.views import MethodView
from flask import Response, abort, request, make_response


class LoginSimulationView(MethodView):
    """
    Simula un portal externo que llama a la API de IAToolkit de servidor a servidor,
    replicando el flujo real de `dispatch_request`.
    Para usarlo, visita /login_test/<company_short_name>/<external_user_id>
    """

    def get(self, company_short_name: str, external_user_id: str):
        api_key = os.getenv("IATOOLKIT_API_KEY")
        base_url = request.host_url.rstrip('/')

        if not api_key:
            abort(500, "Error: IATOOLKIT_API_KEY no está configurada en el servidor de prueba.")
        if not external_user_id:
            abort(400, "Error: Debes proporcionar un external_user_id en la URL.")

        target_url = f"{base_url}/{company_short_name}/external_login"

        # --- INICIO DE LA CORRECCIÓN ---
        # Usamos el formato de header 'Authorization: Bearer' como solicitaste.
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        # --- FIN DE LA CORRECCIÓN ---

        payload = {'external_user_id': external_user_id}

        try:
            # Llamada POST interna. 'stream=True' es importante para manejar la respuesta.
            internal_response = requests.post(target_url, headers=headers, data=json.dumps(payload), timeout=120,
                                              stream=True)
            internal_response.raise_for_status()

            # Creamos una nueva Response de Flask para el navegador del usuario.
            user_response = Response(
                internal_response.iter_content(chunk_size=1024),
                status=internal_response.status_code
            )

            # Copiamos TODAS las cabeceras de la respuesta interna a la respuesta final,
            # incluyendo 'Content-Type' y, crucialmente, 'Set-Cookie'.
            for key, value in internal_response.headers.items():
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection']:
                    user_response.headers[key] = value

            return user_response

        except requests.exceptions.HTTPError as e:
            error_text = f"Error en la llamada interna a la API: {e.response.status_code}. Respuesta: {e.response.text}"
            return Response(error_text, status=e.response.status_code, mimetype='text/plain')
        except requests.exceptions.RequestException as e:
            return Response(f'Error de conexión con el servicio de IA: {str(e)}', status=502, mimetype='text/plain')