# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import redirect, url_for
from common.session_manager import SessionManager
from datetime import datetime, timezone
from injector import inject
from repositories.profile_repo import ProfileRepo
from services.jwt_service import JWTService
import logging
from flask import request
from typing import Optional

MAX_INACTIVITY_SECONDS = 60*30

class IAuthentication:
    @inject

    def __init__(self,
                 profile_repo: ProfileRepo,
                 jwt_service: JWTService):
        self.profile_repo = profile_repo
        self.jwt_service = jwt_service

    def verify(self, company_short_name: str, body_external_user_id: str = None) -> dict:
        # authentication is in this orden: JWT, API Key, Sesión
        local_user_id = None
        company_id = None
        auth_method = None
        external_user_id = None  # for JWT or API Key
        
        # 1. try auth via JWT
        jwt_company_id, jwt_external_user_id, jwt_error_info = self._authenticate_via_chat_jwt(company_short_name)

        if jwt_company_id is not None and jwt_external_user_id is not None:
            auth_method = "JWT"
            company_id = jwt_company_id
            external_user_id = jwt_external_user_id
            local_user_id = 0
        elif jwt_error_info is not None:
            # explicit error in JWT (inválido, expirado, etc.)
            logging.warning(f"Fallo de autenticación JWT: {jwt_error_info}")
            return {"error_message": "Fallo de autenticación JWT"} 
        else:
            # 2. JWT not apply, try by API Key
            api_key_company_id, api_key_error_info = self._authenticate_via_api_key(company_short_name)

            if api_key_company_id is not None:
                auth_method = "API Key"
                company_id = api_key_company_id
                external_user_id = body_external_user_id  # API Key usa external_user_id del body
                local_user_id = 0
            elif api_key_error_info is not None:
                # explicit error in API Key (inválida, incorrecta, error interno)
                logging.warning(f"Fallo de autenticación API Key: {api_key_error_info}")
                return {"error_message": "Fallo de autenticación API Key"}
            else:
                # 3. no JWT and API Key auth, try by Session
                self.check_if_user_is_logged_in(company_short_name)  # raise exception or redirect if not logged in

                # In case not logged in check_if_user_is_logged_in redirects to login page
                auth_method = "Session"
                local_user_id = SessionManager.get('user_id')
                company_id = SessionManager.get('company_id')
                external_user_id = ""

                if not company_id or not local_user_id:
                    logging.error(
                        f"Sesión válida para {company_short_name} pero falta company_id o user_id en SessionManager.")
                    return {"error_message": "Fallo interno en la autenticación o no autenticado"}

        # last verification of authentication
        if company_id is None or auth_method is None or local_user_id is None:
            # Esta condición solo debería alcanzarse si hay un flujo no manejado o un error lógico.
            # Si todos los métodos fallan en autenticar (y no devuelven error explícito antes),
            logging.error(
                f"Fallo inesperado en la lógica de autenticación para {company_short_name}. Ningún método tuvo éxito o devolvió error.")
            return {"error_message": "Fallo interno en la autenticación o no autenticado"}

        return {
            'success': True,
            "auth_method": auth_method,
            "company_id": company_id,
            "auth_method": auth_method,
            "local_user_id": local_user_id,
            "external_user_id": external_user_id
        }

    def _authenticate_via_api_key(self, company_short_name_from_url: str):
        """
        Intenta autenticar usando API Key de los headers.
        Retorna (company_id, None) en éxito.
        Retorna (None, error_message) en fallo.
        """
        api_key_header = request.headers.get('Authorization')
        api_key_value = None

        # extract the key
        if api_key_header and api_key_header.startswith('Bearer '):
            api_key_value = api_key_header.split('Bearer ')[1]
        else:
            # there is no key in the headers expected
            return None, None

        # validate the api-key using ProfileRepo
        try:
            api_key_entry = self.profile_repo.get_active_api_key_entry(api_key_value)
            if not api_key_entry:
                logging.warning(f"Intento de acceso con API Key inválida o inactiva: {api_key_value[:5]}...")
                return None, "API Key inválida o inactiva"

            # check that the key belongs to the company
            # api_key_entry.company already loaded by joinedload
            if not api_key_entry.company or api_key_entry.company.short_name != company_short_name_from_url:
                return None, f"API Key no es válida para la compañía {company_short_name_from_url}"

            # successfull auth by API Key
            company_id = api_key_entry.company_id

            return company_id, None

        except Exception as e:
            logging.exception(f"Error interno durante validación de API Key: {e}")
            return None, "Error interno del servidor al validar API Key"

    def _authenticate_via_chat_jwt(self, company_short_name_from_url: str) -> tuple[
        Optional[int], Optional[str], Optional[str]]:
        """
        Autentica usando un JWT de sesión de chat del header 'X-Chat-Token'.
        Retorna (company_id, external_user_id, None) en éxito.
        Retorna (None, None, error_message) en fallo.
        """
        chat_jwt = request.headers.get('X-Chat-Token')
        if not chat_jwt:
            return None, None, None

        # open the jwt token and retrieve the payload
        jwt_payload = self.jwt_service.validate_chat_jwt(chat_jwt, company_short_name_from_url)
        if not jwt_payload:
            # La validación falló (expirado, firma incorrecta, empresa no coincide, etc.)
            # validate_chat_jwt ya habrá logueado el motivo específico.
            return None, None, "Token de chat expirado, debes reingresar al chat"

        # Éxito: el JWT es válido y corresponde a la empresa y tipo esperados.
        company_id = jwt_payload.get('company_id')
        external_user_id = jwt_payload.get('external_user_id')

        # Sanity check adicional, aunque validate_chat_jwt debería cubrir esto.
        if not isinstance(company_id, int) or not external_user_id:
            logging.error(
                f"LLMQuery: JWT payload incompleto tras validación exitosa. CompanyID: {company_id}, UserID: {external_user_id}")
            return None, None, "Token de chat con formato interno incorrecto"

        return company_id, external_user_id, None

    def check_if_user_is_logged_in(self, company_short_name: str):
        if not SessionManager.get('user'):
            if company_short_name:
                return redirect(url_for('login', company_short_name=company_short_name))
            else:
                return redirect(url_for('home'))

        if company_short_name != SessionManager.get('company_short_name'):
            return redirect(url_for('login', company_short_name=company_short_name))

        # Verificar timeout de inactividad
        if not self.check_session_timeout():
            SessionManager.clear()
            return redirect(url_for('login', company_short_name=company_short_name))

        # update last_activity
        SessionManager.set('last_activity', datetime.now(timezone.utc).timestamp())

    def check_session_timeout(self):
        # get last activity from session manager
        last_activity = SessionManager.get('last_activity')
        if not last_activity:
            return False

        # Tiempo actual en timestamp
        current_time = datetime.now(timezone.utc).timestamp()

        # Calcular el tiempo de inactividad
        inactivity_duration = current_time - last_activity

        # Verificar si se excedió el tiempo máximo de inactividad
        if inactivity_duration > MAX_INACTIVITY_SECONDS:
            # Cerrar sesión o invalidar sesión
            return False  # Sesión caducó

        # Actualizar el timestamp de la última actividad si la sesión sigue activa
        SessionManager.set('last_activity', current_time)

        return True  # Sesión sigue activa





