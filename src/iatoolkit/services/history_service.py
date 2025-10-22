# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from injector import inject
from iatoolkit.repositories.llm_query_repo import LLMQueryRepo
from iatoolkit.repositories.profile_repo import ProfileRepo


class HistoryService:
    @inject
    def __init__(self, llm_query_repo: LLMQueryRepo,
                 profile_repo: ProfileRepo):
        self.llm_query_repo = llm_query_repo
        self.profile_repo = profile_repo

    def get_history(self,
                     company_short_name: str,
                     user_identifier: str) -> dict:
        try:
            # validate company
            company = self.profile_repo.get_company_by_short_name(company_short_name)
            if not company:
                return {'error': f'No existe la empresa: {company_short_name}'}

            history = self.llm_query_repo.get_history(company, user_identifier)

            if not history:
                return {'message': 'Historial vacio actualmente', 'history': []}

            history_list = [query.to_dict() for query in history]

            return {'message': 'Historial obtenido correctamente', 'history': history_list}

        except Exception as e:
            return {'error': str(e)}