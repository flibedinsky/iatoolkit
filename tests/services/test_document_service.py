# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import patch, MagicMock
from services.document_service import DocumentService
from common.exceptions import AppException


class TestDocumentService:

    @pytest.fixture(autouse=True)
    def setup_env_vars(self, monkeypatch):
        """
        Configura las variables de entorno necesarias para DocumentService
        antes de cada test.
        """
        monkeypatch.setenv("MAX_DOC_PAGES", "10")

    def test_initialization(self):
        """Prueba la inicialización de DocumentService con configuración correcta."""
        service = DocumentService()
        assert service.max_doc_pages == 10

    def test_file_txt_when_binary_content(self):
        service = DocumentService()
        result = service.file_to_txt("test.txt", b"dummy_content")
        assert result == "dummy_content"

    def test_file_txt_when_binary_content_and_error_decoding(self):
        service = DocumentService()
        with pytest.raises(AppException) as excinfo:
            result = service.file_to_txt("test.txt", b'\xff\xfe\xff'
)
        assert "FILE_FORMAT_ERROR" == excinfo.value.error_type.name

    def test_file_txt_when_txt_content(self):
        service = DocumentService()
        result = service.file_to_txt("test.txt", "dummy_content")
        assert result == "dummy_content"

    @patch("services.document_service.DocumentService.is_scanned_pdf")
    @patch("services.document_service.DocumentService.read_scanned_pdf", return_value="Scanned text")
    @patch("services.document_service.DocumentService.read_pdf", return_value="PDF text")
    def test_extension_file_detection(
            self, mock_read_pdf, mock_read_scanned_pdf, mock_is_scanned_pdf):

        mock_is_scanned_pdf.return_value = True
        service = DocumentService()
        result = service.file_to_txt("test.pdf", "dummy_content")

        assert result == "Scanned text"

        mock_is_scanned_pdf.return_value = False
        result = service.file_to_txt("test.pdf", "dummy_content")
        assert result == "PDF text"


    @patch("services.document_service.io")
    @patch("services.document_service.Document")
    def test_read_docx_successful(self, mock_document, mock_io):
        """Prueba que un archivo .docx se lea correctamente."""
        mock_io.BytesIO.return_value = b'a file'
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="First paragraph"),
            MagicMock(text="Second paragraph"),
        ]
        mock_document.return_value = mock_doc

        service = DocumentService()
        content = service.read_docx("dummy_docx_content")
        assert content == "# First paragraph\n\n# Second paragraph\n\n"

    @patch("services.document_service.fitz.open")
    def test_read_pdf_successful(self, mock_fitz_open):
        """Prueba que un archivo PDF con prompt_llm.txt se lea correctamente."""
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__iter__.return_value = [
            MagicMock(get_text=MagicMock(return_value="Page 1 text")),
            MagicMock(get_text=MagicMock(return_value="Page 2 text")),
        ]
        mock_fitz_open.return_value = mock_pdf

        service = DocumentService()
        content = service.read_pdf("dummy_pdf_content")
        assert content == "Page 1 textPage 2 text"

    @patch("services.document_service.pytesseract.image_to_string", return_value="Scanned text")
    @patch("services.document_service.Image.frombytes")
    @patch("services.document_service.fitz.Pixmap")
    @patch("services.document_service.fitz.open")
    def test_read_scanned_pdf(self, mock_fitz_open, mock_pixmap, mock_frombytes, mock_tesseract):
        """Prueba que un PDF escaneado convierta imágenes en prompt_llm.txt correctamente."""
        mock_pdf = MagicMock()
        mock_pdf.page_count = 2
        mock_pdf.__len__.return_value = 1
        mock_fitz_open.return_value = mock_pdf

        mock_pdf.__iter__.return_value = [
            MagicMock(get_images=MagicMock(return_value=[(1,)]))
        ]
        mock_pdf.__getitem__.return_value = MagicMock(get_images=MagicMock(return_value=[(1,)]))

        mock_pixmap_obj = MagicMock()
        mock_pixmap.return_value = mock_pixmap_obj

        # Simular retorno de atributos del Pixmap
        mock_pixmap_obj.n = 3
        mock_pixmap_obj.width = 100
        mock_pixmap_obj.height = 100
        mock_pixmap_obj.samples = b"dummy_pixels"

        mock_fitz_open.return_value[0].get_images.return_value = [(1,)]
        mock_fitz_open.return_value[0].__getitem__ = MagicMock(return_value=mock_pixmap)

        service = DocumentService()
        content = service.read_scanned_pdf(b"dummy_scanned_pdf_content")
        assert content == "Scanned text"

    @patch("services.document_service.fitz.open")  # Parcheamos fitz.open
    def test_is_scanned_pdf_with_selectable_text(self, mock_fitz_open):
        """Prueba que un PDF con prompt_llm.txt seleccionable retorne False."""
        # Mock del documento PDF con prompt_llm.txt seleccionable
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 1  # Simula 1 página
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is some selectable text"
        mock_pdf.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_pdf

        service = DocumentService()
        result = service.is_scanned_pdf(b"dummy_pdf_content")
        assert result is False  # Tiene prompt_llm.txt seleccionable, no es escaneado

    @patch("services.document_service.fitz.open")  # Parcheamos fitz.open
    def test_is_scanned_pdf_with_scanned_images(self, mock_fitz_open):
        """Prueba que un PDF con imágenes (escaneado) retorne True."""
        # Mock del documento PDF con imágenes
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 1  # Simula 1 página
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # No hay prompt_llm.txt
        mock_page.get_images.return_value = [(1,)]  # Hay imágenes
        mock_pdf.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_pdf

        service = DocumentService()
        result = service.is_scanned_pdf(b"dummy_pdf_content")
        assert result is True  # Escaneado, tiene imágenes pero no prompt_llm.txt

    @patch("services.document_service.fitz.open")  # Parcheamos fitz.open
    def test_is_scanned_pdf_without_text_or_images(self, mock_fitz_open):
        """Prueba que un PDF sin prompt_llm.txt y sin imágenes retorne True."""
        # Mock del documento PDF vacío (no tiene prompt_llm.txt ni imágenes)
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 1  # Simula 1 página
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # No hay prompt_llm.txt
        mock_page.get_images.return_value = []  # No hay imágenes
        mock_pdf.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_pdf

        service = DocumentService()
        result = service.is_scanned_pdf(b"dummy_pdf_content")
        assert result is True  # No tiene prompt_llm.txt ni imágenes, probablemente escaneado

    @patch("services.document_service.fitz.open")  # Parcheamos fitz.open
    def test_is_scanned_pdf_with_empty_pdf(self, mock_fitz_open):
        """Prueba que un PDF vacío (sin páginas) retorne True."""
        # Mock del documento PDF vacío (sin páginas)
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 0  # Sin páginas
        mock_fitz_open.return_value = mock_pdf

        service = DocumentService()
        result = service.is_scanned_pdf(b"dummy_pdf_content")
        assert result is True  # Al no tener páginas, se considera escaneado
