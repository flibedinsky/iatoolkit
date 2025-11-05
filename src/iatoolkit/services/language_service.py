# iatoolkit/services/language_service.py

import logging
from injector import inject
from flask import g, request
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.common.session_manager import SessionManager


class LanguageService:
    """
    Determines the correct language for the current request
    based on a defined priority order (session, URL, etc.)
    and caches it in the Flask 'g' object for the request's lifecycle.
    """

    @inject
    def __init__(self, profile_repo: ProfileRepo):
        self.profile_repo = profile_repo

    def _get_company_short_name(self) -> str | None:
        """
        Gets the company_short_name from the current request context.
        This handles different scenarios like web sessions, public URLs, and API calls.

        Priority Order:
        1. Flask Session (for logged-in web users).
        2. URL rule variable (for public pages and API endpoints).
        """
        # 1. Check session for logged-in users
        company_short_name = SessionManager.get('company_short_name')
        if company_short_name:
            return company_short_name

        # 2. Check URL arguments (e.g., /<company_short_name>/login)
        # This covers public pages and most API calls.
        if request.view_args and 'company_short_name' in request.view_args:
            return request.view_args['company_short_name']

        return None

    def get_current_language(self) -> str:
        """
        Determines and caches the language for the current request using a priority order:
        1. User's preference (from their profile).
        2. Company's default language.
        3. System-wide fallback language ('es').
        """
        if 'lang' in g:
            return g.lang

        from iatoolkit.services.i18n_service import I18nService
        lang = I18nService.FALLBACK_LANGUAGE

        try:
            company_short_name = self._get_company_short_name()
            if company_short_name:
                # Prioridad 1: Preferencia del Usuario
                user_identifier = SessionManager.get('user_identifier')
                if user_identifier:
                    # Usamos el repositorio para obtener el objeto User
                    user = self.profile_repo.get_user_by_email(
                        user_identifier)  # Asumiendo que el email es el identificador
                    if user and user.preferred_language:
                        g.lang = user.preferred_language
                        return g.lang

                # Prioridad 2: Idioma por defecto de la Compañía (si no se encontró preferencia de usuario)
                company = self.profile_repo.get_company_by_short_name(company_short_name)
                if company and company.default_language:
                    lang = company.default_language
        except Exception as e:
            logging.debug(f"Could not determine language, falling back to default. Reason: {e}")
            pass

        g.lang = lang
        return lang