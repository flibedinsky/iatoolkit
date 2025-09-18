# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from common.exceptions import AppException
from repositories.vs_repo import VSRepo
from repositories.models import VSDoc, Document


class TestVSRepo:
    @pytest.fixture
    def mock_db_manager(self):
        """Fixture para mockear el DatabaseManager."""
        mock_manager = MagicMock()
        mock_session = MagicMock()
        mock_manager.get_session.return_value = mock_session
        return mock_manager

    @pytest.fixture
    def mock_embedder(self):
        """Fixture para mockear el modelo de SentenceTransformer."""
        with patch('repositories.vs_repo.InferenceClient') as MockEmbedder:
            mock_instance = MockEmbedder.return_value
            mock_instance.feature_extraction.return_value = [0.1, 0.2, 0.3]  # Retorna un embedding simulado
            yield mock_instance

    @pytest.fixture
    def vs_repo(self, mock_db_manager, mock_embedder):
        """Fixture para inicializar el repositorio VSRepo con dependencias mockeadas."""
        return VSRepo(mock_db_manager)

    def test_add_document_rollback_on_error(self, vs_repo, mock_db_manager, mock_embedder):
        """Prueba que verifica el rollback cuando ocurre un error en add_document."""
        mock_session = mock_db_manager.get_session.return_value

        mock_embedder.feature_extraction.side_effect = Exception("Error al generar embeddings")
        vs_chunk_list = [VSDoc(id=1, text="Documento con error")]

        with pytest.raises(AppException) as excinfo:
            vs_repo.add_document(vs_chunk_list)

        assert excinfo.value.error_type == AppException.ErrorType.DATABASE_ERROR
        assert "Error insertando documentos en PostgreSQL" in str(excinfo.value)
        mock_session.rollback.assert_called_once()

    def test_add_document_success(self, vs_repo, mock_db_manager, mock_embedder):
        mock_session = mock_db_manager.get_session.return_value

        vs_chunk_list = [
            VSDoc(id=1, text="Documento de prueba 1"),
            VSDoc(id=2, text="Documento de prueba 2")
        ]

        vs_repo.add_document(vs_chunk_list)

        # Verificar que las embeddings se generaron y los documentos fueron añadidos
        assert mock_embedder.feature_extraction.call_count == len(vs_chunk_list)
        assert mock_session.add.call_count == len(vs_chunk_list)
        mock_session.commit.assert_called_once()


    def test_query_raises_exception_on_error(self, vs_repo, mock_db_manager, mock_embedder):
        mock_session = mock_db_manager.get_session.return_value
        mock_session.execute.side_effect = Exception("Error en la base de datos")

        with pytest.raises(AppException) as excinfo:
            vs_repo.query(company_id=123, query_text="texto de prueba", n_results=3)

        assert excinfo.value.error_type == AppException.ErrorType.DATABASE_ERROR
        assert "Error en la consulta" in str(excinfo.value)

    def test_query_success(self, vs_repo, mock_db_manager, mock_embedder):
        mock_session = mock_db_manager.get_session.return_value

        # Simular resultados de la consulta en la base de datos
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "filename1.txt", "contenido1", 'conb64'),
            (2, "filename2.txt", "contenido2", 'conb64')
        ]

        result = vs_repo.query(company_id=123, query_text="prompt_llm.txt de prueba", n_results=2)

        # Verificar resultados
        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].filename == "filename1.txt"
        assert result[0].content == "contenido1"
        mock_embedder.feature_extraction.assert_called_once_with(["prompt_llm.txt de prueba"])


    def test_remove_duplicates_by_id(self, vs_repo):
        """Prueba para verificar la eliminación de duplicados por ID."""
        documents = [
            Document(id=1, company_id=123, filename="doc1.txt", content="contenido1", content_b64=''),
            Document(id=2, company_id=123, filename="doc2.txt", content="contenido2", content_b64=''),
            Document(id=1, company_id=123, filename="doc1.txt", content="contenido1", content_b64=''),  # Duplicado
        ]

        result = vs_repo.remove_duplicates_by_id(documents)

        # Verificar que solo queden 2 documentos
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
