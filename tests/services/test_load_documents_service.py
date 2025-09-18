# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import patch, MagicMock, ANY
from services.load_documents_service import LoadDocumentsService
from repositories.models import Company
from common.exceptions import AppException


class TestLoadDocumentsService:
    def setup_method(self):
        self.mock_vector_store = MagicMock()
        self.mock_file_connector_factory = MagicMock()
        self.mock_dispatcher = MagicMock()
        self.mock_doc_service = MagicMock()
        self.mock_doc_repo = MagicMock()
        self.mock_profile_repo = MagicMock()
        self.mock_llm_query_repo = MagicMock()

        self.service = LoadDocumentsService(
            doc_service=self.mock_doc_service,
            doc_repo=self.mock_doc_repo,
            profile_repo=self.mock_profile_repo,
            llm_query_repo=self.mock_llm_query_repo,
            vector_store=self.mock_vector_store,
            file_connector_factory=self.mock_file_connector_factory,
            dispatcher=self.mock_dispatcher
        )

        self.company = Company(
            id=1,
            name='a big company',
            short_name='company',
            parameters={
                "load": {
                    "document_types": {
                        "certificados":
                            {
                                "connector": {"type": "s3", "bucket": "test-bucket"},
                                "metadata": {"document_type": "certificate"}
                            }
                    }
                }
            }
        )
        self.mock_profile_repo.get_companies.return_value = [self.company]

    def test_load_when_no_services_to_load(self):
        self.mock_profile_repo.get_companies.return_value = []
        result = self.service.load()

        assert result == {'message': '0 files processed'}

    def test_load_when_missing_connector(self):
        self.company.parameters['load']['document_types']['certificados']['connector'] = None

        with pytest.raises(AppException) as excinfo:
            self.service.load('certificados')

        assert excinfo.value.error_type == AppException.ErrorType.MISSING_PARAMETER
        assert "Falta configurar conector" in str(excinfo.value)


    @patch("logging.exception")
    def test_load_data_source_when_exception(self, mock_logging_exception):
        mock_connector_config = {"type": "s3"}
        self.mock_file_connector_factory.create.side_effect = Exception("Test exception")

        result = self.service.load_data_source(mock_connector_config)

        assert result == {"error": "Test exception"}
        mock_logging_exception.assert_called_once_with("Loading files error: %s", "Test exception")


    def test_load_file_when_document_exists(self, ):
        filename = "mock_file.pdf"
        content = b"mock content"
        self.mock_doc_repo.get.return_value = True

        self.service.load_file(filename, content)

        self.mock_doc_repo.get.assert_called_once_with(company=self.service.company, filename=filename)
        self.service.doc_service.file_to_txt.assert_not_called()
        self.mock_doc_repo.insert.assert_not_called()
        self.service.vector_store.add_document.assert_not_called()

    def test_load_files_when_exception_adding_document(self):
        self.mock_doc_repo.get.return_value = None
        self.mock_vector_store.add_document.side_effect = Exception("Error adding document")

        filename = "mock_file.pdf"
        content = b"mock content"
        with pytest.raises(AppException) as excinfo:
            result = self.service.load_file(filename, content, self.company)

        assert excinfo.value.error_type == AppException.ErrorType.LOAD_DOCUMENT_ERROR
        assert "Error al procesar el archivo" in str(excinfo.value)

    @patch("services.load_documents_service.FileProcessor")
    def test_load_files_success(self, mock_file_processor):
        mock_connector_config = {"type": "s3", "bucket": "test-bucket"}

        # Mock del FileProcessor
        mock_processor_instance = MagicMock()
        mock_processor_instance.processed_files = 2
        mock_file_processor.return_value = mock_processor_instance

        # Mock del conector
        mock_connector = MagicMock()
        self.mock_file_connector_factory.create.return_value = mock_connector

        result = self.service.load()

        assert result == {'message': '2 files processed'}
        self.mock_file_connector_factory.create.assert_called_with(mock_connector_config)
        mock_file_processor.assert_called_once_with(mock_connector, ANY)
        mock_processor_instance.process_files.assert_called_once()

    def test_load_when_file_is_created(self):
        # Mock del archivo y contenido
        filename = "mock_file.pdf"
        content = b"mock content"
        self.service.company = self.company
        context = {'metadata': {"document_type": "certificate"}}

        # Mock simulando que el archivo no existe
        self.mock_doc_repo.get.return_value = None

        # Mock de extracción de texto
        extracted_text = "mock extracted content"
        self.service.doc_service.file_to_txt.return_value = extracted_text
        self.mock_dispatcher.get_metadata_from_filename.return_value = {}

        self.service.load_file(filename=filename, content=content, context=context)

        # Verificaciones
        self.mock_doc_repo.get.assert_called_once_with(company=self.company, filename=filename)
        self.service.doc_service.file_to_txt.assert_called_once_with(filename, content)
        self.service.vector_store.add_document.assert_called_once()