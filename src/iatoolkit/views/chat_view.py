# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from flask import render_template, request, jsonify
from iatoolkit.services.profile_service import ProfileService
from flask.views import MethodView
from injector import inject
import os
from iatoolkit.common.auth import IAuthentication
from iatoolkit.services.prompt_manager_service import PromptService
from iatoolkit.services.branding_service import BrandingService


class ChatView(MethodView):
    @inject
    def __init__(self,
                 iauthentication: IAuthentication,
                 prompt_service: PromptService,
                 profile_service: ProfileService,
                 branding_service: BrandingService
                 ):
        self.iauthentication = iauthentication
        self.profile_service = profile_service
        self.prompt_service = prompt_service
        self.branding_service = branding_service

    def get(self, company_short_name: str):
        # get access credentials
        iaut = self.iauthentication.verify(company_short_name)
        if not iaut.get("success"):
            return jsonify(iaut), 401

        user_agent = request.user_agent
        is_mobile = user_agent.platform in ["android", "iphone", "ipad"] or "mobile" in user_agent.string.lower()
        alert_message = request.args.get('alert_message', None)

        # 1. get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        # 2. get the company prompts
        prompts = self.prompt_service.get_user_prompts(company_short_name)

        # 3. get the  branding data
        branding_data = self.branding_service.get_company_branding(company)

        return render_template("chat.html",
                               branding=branding_data,
                               company_short_name=company_short_name,
                               is_mobile=is_mobile,
                               alert_message=alert_message,
                               alert_icon='success' if alert_message else None,
                               iatoolkit_base_url=os.getenv('IATOOLKIT_BASE_URL', 'http://localhost:5000'),
                               prompts=prompts
                               )
