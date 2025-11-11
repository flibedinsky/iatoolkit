# tests/services/test_load_documents_service.py

import pytest
from unittest.mock import MagicMock, patch, call
from iatoolkit.services.load_documents_service import LoadDocumentsService
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.infra.connectors.file_connector_factory import FileConnectorFactory
from iatoolkit.services.document_service import DocumentService
from iatoolkit.repositories.document_repo import DocumentRepo
from iatoolkit.repositories.vs_repo import VSRepo
from iatoolkit.services.dispatcher_service import Dispatcher
from iatoolkit.repositories.models import Company, Document
from iatoolkit.common.exceptions import IAToolkitException

# Mock configuration to simulate the 'knowledge_base' section of company.yaml
MOCK_KNOWLEDGE_BASE_CONFIG = {
    'connectors': {
        'development': {'type': 'local'},
        'production': {'type': 's3', 'bucket': 'prod_bucket', 'prefix': 'prod_prefix'}
    },
    'document_sources': {
        'contracts': {'path': 'data/contracts', 'metadata': {'category': 'legal'}},
        'manuals': {'path': 'data/manuals', 'metadata': {'category': 'guide'}}
    }
}


class TestLoadDocumentsService:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up mocks for all dependencies and instantiate the service."""
        self.mock_config_service = MagicMock(spec=ConfigurationService)
        self.mock_file_connector_factory = MagicMock(spec=FileConnectorFactory)
        self.mock_doc_service = MagicMock(spec=DocumentService)
        self.mock_doc_repo = MagicMock(spec=DocumentRepo)
        self.mock_vector_store = MagicMock(spec=VSRepo)
        self.mock_dispatcher = MagicMock(spec=Dispatcher)

        # SOLUCIÓN: Crear un mock para 'session' y adjuntarlo al mock del repositorio.
        self.mock_session = MagicMock()
        self.mock_doc_repo.session = self.mock_session

        self.service = LoadDocumentsService(
            config_service=self.mock_config_service,
            file_connector_factory=self.mock_file_connector_factory,
            doc_service=self.mock_doc_service,
            doc_repo=self.mock_doc_repo,
            vector_store=self.mock_vector_store,
            dispatcher=self.mock_dispatcher
        )
        self.company = Company(id=1, short_name='acme')

    def test_load_sources_raises_exception_if_knowledge_base_config_is_missing(self):
        self.mock_config_service.get_configuration.return_value = None
        with pytest.raises(IAToolkitException) as excinfo:
            self.service.load_sources(self.company, sources_to_load=['contracts'])
        assert excinfo.value.error_type == IAToolkitException.ErrorType.CONFIG_ERROR

    @patch('iatoolkit.services.load_documents_service.os.getenv', return_value='dev')  # CORREGIDO: 'dev'
    @patch('iatoolkit.services.load_documents_service.FileProcessor')
    def test_load_sources_uses_dev_connector_in_development(self, MockFileProcessor, mock_getenv):
        self.mock_config_service.get_configuration.return_value = MOCK_KNOWLEDGE_BASE_CONFIG
        self.service.load_sources(self.company, sources_to_load=['contracts'])
        self.mock_file_connector_factory.create.assert_called_once_with({
            'type': 'local',
            'path': 'data/contracts'
        })
        MockFileProcessor.assert_called_once()

    @patch('iatoolkit.services.load_documents_service.os.getenv', return_value='production')
    @patch('iatoolkit.services.load_documents_service.FileProcessor')
    def test_load_sources_uses_prod_connector_in_production(self, MockFileProcessor, mock_getenv):
        self.mock_config_service.get_configuration.return_value = MOCK_KNOWLEDGE_BASE_CONFIG
        self.service.load_sources(self.company, sources_to_load=['manuals'])
        self.mock_file_connector_factory.create.assert_called_once_with({
            'type': 's3',
            'bucket': 'prod_bucket',
            'prefix': 'prod_prefix',
            'path': 'data/manuals'
        })

    def test_load_sources_raises_exception_if_no_sources_provided(self):
        """
        GIVEN sources_to_load is None or empty
        WHEN load_company_sources is called
        THEN it should raise a parameter error, as per the service logic.
        """
        self.mock_config_service.get_configuration.return_value = MOCK_KNOWLEDGE_BASE_CONFIG
        with pytest.raises(IAToolkitException) as excinfo:
            # CORREGIDO: Este test ahora verifica que se lance la excepción.
            self.service.load_sources(self.company)
        assert excinfo.value.error_type == IAToolkitException.ErrorType.PARAM_NOT_FILLED

    def test_callback_skips_processing_if_document_exists(self):
        self.mock_doc_repo.get.return_value = MagicMock()
        self.service._file_processing_callback(self.company, 'existing.pdf', b'content')
        self.mock_doc_service.file_to_txt.assert_not_called()
        self.mock_vector_store.add_document.assert_not_called()
        self.mock_session.commit.assert_not_called()


    def test_callback_rolls_back_on_exception(self):
        self.mock_doc_repo.get.return_value = None
        self.mock_doc_service.file_to_txt.return_value = "text"
        self.mock_vector_store.add_document.side_effect = Exception("Vector DB is down")
        with pytest.raises(IAToolkitException) as excinfo:
            self.service._file_processing_callback(self.company, 'fail.pdf', b'content')
        assert excinfo.value.error_type == IAToolkitException.ErrorType.LOAD_DOCUMENT_ERROR
        self.mock_session.rollback.assert_called_once()
        self.mock_session.commit.assert_not_called()