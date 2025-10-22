from flask.views import MethodView
from flask import request, jsonify
from injector import inject
from iatoolkit.services.query_service import QueryService
from iatoolkit.services.auth_service import AuthService  # Use AuthService for session check


class LLMQueryWebView(MethodView):  # Renamed for clarity
    """
    Web-only endpoint for submitting queries from the chat UI.
    Authenticates via Flask session cookie.
    """

    @inject
    def __init__(self, auth_service: AuthService, query_service: QueryService):
        self.auth_service = auth_service
        self.query_service = query_service

    def post(self, company_short_name: str):
        # 1. Authenticate the web session request.
        auth_result = self.auth_service.verify()
        if not auth_result.get("success"):
            return jsonify({"error": auth_result.get("error_message")}), auth_result.get("status_code", 401)

        # 2. Get the guaranteed user_identifier from the auth result.
        user_identifier = auth_result['user_identifier']
        data = request.get_json() or {}

        # 3. Call the unified query service method.
        result = self.query_service.llm_query(
            company_short_name=company_short_name,
            user_identifier=user_identifier,
            question=data.get('question', ''),
            prompt_name=data.get('prompt_name'),
            client_data=data.get('client_data', {}),
            files=data.get('files', [])
        )
        return jsonify(result)