# tests/repositories/test_vs_repo.py

import pytest
from unittest.mock import MagicMock, call
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.repositories.vs_repo import VSRepo
from iatoolkit.repositories.models import VSDoc, Document, Company
from iatoolkit.services.embedding_service import EmbeddingService
from iatoolkit.repositories.database_manager import DatabaseManager


class TestVSRepo:
    MOCK_COMPANY_SHORT_NAME = "test-corp"
    MOCK_COMPANY_ID = 123
    MOCK_EMBEDDING_VECTOR = [0.1, 0.2, 0.3]

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up mocks and instantiate VSRepo before each test."""
        # Mock dependencies
        self.mock_db_manager = MagicMock(spec=DatabaseManager)
        self.mock_session = self.mock_db_manager.get_session.return_value
        self.mock_embedding_service = MagicMock(spec=EmbeddingService)

        # Instantiate the class under test
        self.vs_repo = VSRepo(
            db_manager=self.mock_db_manager,
            embedding_service=self.mock_embedding_service
        )

        # Default mock behavior
        self.mock_embedding_service.embed_text.return_value = self.MOCK_EMBEDDING_VECTOR

    def test_add_document_success(self):
        """Tests that add_document correctly generates embeddings and commits to the DB."""
        # Arrange
        vs_chunk_list = [
            VSDoc(id=1, text="Documento de prueba 1"),
            VSDoc(id=2, text="Documento de prueba 2")
        ]

        # Act
        self.vs_repo.add_document(self.MOCK_COMPANY_SHORT_NAME, vs_chunk_list)

        # Assert
        # Check that embed_text was called for each document with the correct context
        expected_calls = [
            call(self.MOCK_COMPANY_SHORT_NAME, "Documento de prueba 1" ),
            call(self.MOCK_COMPANY_SHORT_NAME, "Documento de prueba 2")
        ]
        self.mock_embedding_service.embed_text.assert_has_calls(expected_calls)

        # Check database interactions
        assert self.mock_session.add.call_count == 2
        self.mock_session.commit.assert_called_once()
        self.mock_session.rollback.assert_not_called()

    def test_add_document_rollback_on_embedding_error(self):
        """Tests that a DB rollback occurs if the embedding service fails."""
        # Arrange
        self.mock_embedding_service.embed_text.side_effect = Exception("Embedding service unavailable")
        vs_chunk_list = [VSDoc(id=1, text="Documento con error")]

        # Act & Assert
        with pytest.raises(IAToolkitException):
            self.vs_repo.add_document(self.MOCK_COMPANY_SHORT_NAME, vs_chunk_list)

        self.mock_session.rollback.assert_called_once()
        self.mock_session.commit.assert_not_called()

    def test_query_success(self):
        """Tests the happy path for the query method."""
        # Arrange
        # Mock the lookup for company_id from company_short_name
        mock_company = Company(id=self.MOCK_COMPANY_ID, short_name=self.MOCK_COMPANY_SHORT_NAME)
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = mock_company

        # Mock the final DB query result
        db_rows = [(1, "file1.txt", "content1", "b64_1", {}), (2, "file2.txt", "content2", "b64_2", {})]
        self.mock_session.execute.return_value.fetchall.return_value = db_rows

        # Act
        result_docs = self.vs_repo.query(company_short_name=self.MOCK_COMPANY_SHORT_NAME, query_text="test query")

        # Assert
        # 1. Check embedding service was called
        self.mock_embedding_service.embed_text.assert_called_once_with(self.MOCK_COMPANY_SHORT_NAME, "test query")

        # 2. Check company lookup
        self.mock_session.query.assert_called_once_with(Company)

        # 3. Check final results
        assert len(result_docs) == 2
        assert result_docs[0].id == 1
        assert result_docs[0].filename == "file1.txt"
        assert result_docs[0].company_id == self.MOCK_COMPANY_ID

    def test_query_raises_exception_on_db_error(self):
        """Tests that an IAToolkitException is raised if the DB query fails."""
        # Arrange
        mock_company = Company(id=self.MOCK_COMPANY_ID, short_name=self.MOCK_COMPANY_SHORT_NAME)
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = mock_company
        self.mock_session.execute.side_effect = Exception("Database connection failed")

        # Act & Assert
        with pytest.raises(IAToolkitException, match="Error en la consulta"):
            self.vs_repo.query(company_short_name=self.MOCK_COMPANY_SHORT_NAME, query_text="test query")

    def test_query_raises_exception_for_unknown_company(self):
        """Tests that an exception is raised if the company_short_name does not exist."""
        # Arrange: Simulate that the company is not found
        self.mock_session.query.return_value.filter.return_value.one_or_none.return_value = None

        # Act & Assert
        with pytest.raises(IAToolkitException,
                           match=f"Company with short name '{self.MOCK_COMPANY_SHORT_NAME}' not found"):
            self.vs_repo.query(company_short_name=self.MOCK_COMPANY_SHORT_NAME, query_text="test query")

        self.mock_embedding_service.embed_text.assert_called_once()
        self.mock_session.execute.assert_not_called()

    def test_remove_duplicates_by_id(self):
        """Tests the static-like helper method for removing duplicate documents."""
        # Arrange
        documents = [
            Document(id=1, company_id=1, filename="doc1.txt", content="c1"),
            Document(id=2, company_id=1, filename="doc2.txt", content="c2"),
            Document(id=1, company_id=1, filename="doc1_copy.txt", content="c1_copy"),  # Duplicate ID
        ]

        # Act
        result = self.vs_repo.remove_duplicates_by_id(documents)

        # Assert
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2