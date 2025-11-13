# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.vs_repo import VSRepo
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Company
from injector import inject


class SearchService:
    @inject
    def __init__(self,
                 profile_repo: ProfileRepo,
                 doc_repo: DocumentRepo,
                 vs_repo: VSRepo):
        self.profile_repo = profile_repo
        self.vs_repo = vs_repo
        self.doc_repo = doc_repo

    def search(self, company_short_name: str, query: str, metadata_filter: dict = None) -> str:
        """
        Performs a semantic search for a given query within a company's documents.

        This method queries the vector store for relevant documents based on the
        provided query text. It then constructs a formatted string containing the
        content of the retrieved documents, which can be used as context for an LLM.

        Args:
            company_short_name: The  company to search within.
            query: The text query to search for.
            metadata_filter: An optional dictionary to filter documents by their metadata.

        Returns:
            A string containing the concatenated content of the found documents,
            formatted to be used as a context.
        """
        company = self.profile_repo.get_company_by_short_name(company_short_name)
        if not company:
            return f"error: company {company_short_name} not found"

        document_list = self.vs_repo.query(company_short_name=company_short_name,
                                           query_text=query,
                                           metadata_filter=metadata_filter)

        search_context = ''
        for doc in document_list:
            search_context += f'documento "{doc.filename}"'
            if doc.meta and 'document_type' in doc.meta:
                search_context += f' tipo: {doc.meta.get('document_type', '')}'
            search_context += f': {doc.content}\n'

        return search_context
