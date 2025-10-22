# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask import request
from injector import inject
from iatoolkit.services.profile_service import ProfileService


class AuthService:
    """
    Centralized service for handling authentication for all incoming requests.
    It determines the user's identity based on either a Flask session cookie or an API Key.
    """

    @inject
    def __init__(self, profile_service: ProfileService):
        """
        Injects ProfileService to access session information and validate API keys.
        """
        self.profile_service = profile_service

    def verify(self) -> dict:
        """
        Verifies the current request and identifies the user.

        Returns a dictionary with:
        - success: bool
        - user_identifier: str (if successful)
        - company_short_name: str (if successful)
        - error_message: str (on failure)
        - status_code: int (on failure)
        """
        # --- Priority 1: Check for a valid Flask web session ---
        session_info = self.profile_service.get_current_session_info()
        if session_info and session_info.get('user_identifier'):
            # User is authenticated via a web session cookie.
            return {
                "success": True,
                "user_identifier": session_info['user_identifier'],
                "company_short_name": session_info['company_short_name']
            }

        # --- Priority 2: Check for a valid API Key in headers ---
        api_key = request.headers.get('X-Api-Key')
        if api_key:
            api_key_entry = self.profile_service.get_active_api_key_entry(api_key)
            if not api_key_entry:
                return {"success": False, "error_message": "Invalid or inactive API Key", "status_code": 401}

            # For API calls, the external_user_id must be provided in the request.
            # This check is now the responsibility of the API endpoint view itself.
            company = api_key_entry.company
            return {
                "success": True,
                # For API calls, the user_identifier is not known at this stage,
                # but we know the company. The view will extract the user ID.
                "company_short_name": company.short_name
            }

        # --- Failure: No valid credentials found ---
        return {"success": False, "error_message": "Authentication required. No session cookie or API Key provided.",
                "status_code": 401}