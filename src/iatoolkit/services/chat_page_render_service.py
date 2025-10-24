# iatoolkit/services/chat_page_render_service.py
# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import os
from flask import render_template
from injector import inject
from iatoolkit.services.profile_service import ProfileService
from iatoolkit.services.prompt_manager_service import PromptService
from iatoolkit.services.branding_service import BrandingService

class ChatPageRenderService:
    """
    Service dedicated to collecting the necessary data and rendering
    the chat page.
    """
    @inject
    def __init__(self,
                 profile_service: ProfileService,
                 prompt_service: PromptService,
                 branding_service: BrandingService):
        self.profile_service = profile_service
        self.prompt_service = prompt_service
        self.branding_service = branding_service

    def render_chat_page(self, company_short_name: str, company):
        """
        Collects all necessary data and renders the chat.html template.
        """
        session_info = self.profile_service.get_current_session_info()
        user_profile = session_info.get('profile', {})
        prompts = self.prompt_service.get_user_prompts(company_short_name)
        branding_data = self.branding_service.get_company_branding(company)

        return render_template(
            "chat.html",
            user_is_local=user_profile.get('user_is_local'),
            user_email=user_profile.get('user_email'),
            branding=branding_data,
            prompts=prompts,
            iatoolkit_base_url=os.getenv('IATOOLKIT_BASE_URL')
        )