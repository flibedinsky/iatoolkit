# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask.views import MethodView
from flask import request, redirect, render_template, url_for
from injector import inject
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.query_service import QueryService
from iatoolkit.views.base_login_view import BaseLoginView
from iatoolkit.services.chat_page_render_service import ChatPageRenderService


class LoginView(BaseLoginView):
    """
    Handles login for local users.
    Authenticates and then delegates the path decision (fast/slow) to the base class.
    """

    def post(self, company_short_name: str):
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        email = request.form.get('email')
        password = request.form.get('password')

        # 1. Authenticate user and create the unified session.
        auth_response = self.profile_service.login(
            company_short_name=company_short_name,
            email=email,
            password=password
        )

        if not auth_response['success']:
            return render_template(
                'index.html',
                company_short_name=company_short_name,
                company=company,
                form_data={"email": email},
                alert_message=auth_response["message"]
            ), 400

        user_identifier = auth_response['user_identifier']

        # 2. Delegate the path decision to the centralized logic.
        try:
            return self._handle_login_path(company_short_name, user_identifier, company)
        except Exception as e:
            return render_template("error.html", company=company, company_short_name=company_short_name,
                                   message=f"Error processing login path: {str(e)}"), 500


class FinalizeContextView(MethodView):
    """
    Finalizes context loading in the slow path.
    This view is invoked by the iframe inside onboarding_shell.html.
    """

    @inject
    def __init__(self,
                 profile_service: ProfileService,
                 query_service: QueryService,
                 chat_page_render_service: ChatPageRenderService):
        self.profile_service = profile_service
        self.query_service = query_service
        self.render_service = chat_page_render_service

    def get(self, company_short_name: str):
        # 1. Use the centralized method to get session info.
        session_info = self.profile_service.get_current_session_info()
        user_identifier = session_info.get('user_identifier')

        if not user_identifier:
            # This can happen if the session expires or is invalid.
            return redirect(url_for('login_page', company_short_name=company_short_name))

        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        try:
            # 2. Finalize the context rebuild (the heavy task).
            self.query_service.finalize_context_rebuild(
                company_short_name=company_short_name,
                user_identifier=user_identifier
            )

            # 3. Use the centralized service to render the chat page.
            return self.render_service.render_chat_page(company_short_name, company)

        except Exception as e:
            return render_template("error.html",
                                   company=company,
                                   company_short_name=company_short_name,
                                   message=f"An unexpected error occurred during context loading: {str(e)}"), 500