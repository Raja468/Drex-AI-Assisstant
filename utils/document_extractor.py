"""
utils/document_extractor.py — OCR & Document Understanding for DREX

Provides foundational support for extracting text from images and PDFs.
This enables DREX to understand and process visual and document-based content.

Architecture:
  - Modular utility layer, independent of AI providers
  - pytesseract for image OCR (requires Tesseract installed)
  - pymupdf / pdfplumber for PDF text extraction
  - Clean interface for future AI integration hooks

Capabilities:
  - Extract text from image files (PNG, JPG, etc.)
  - Extract text from PDF files
  - Summarize extracted content (via AI integration hook)
  - Detect if OCR is available on the system

Requirements:
  pip install pytesseract pillow
  pip install pymupdf pdfplumber
  # Tesseract OCR engine must be installed separately:
  #   Windows: https://github.com/UB-Mannheim/tesseract/wiki
  #   Linux:   sudo apt install tesseract-ocr
  #   macOS:   brew install tesseract
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger


class DocumentExtractor:
    """
    Extract text from images and PDFs.

    Uses multiple backends with automatic fallback:
      - pytesseract (OCR for images)
      - pymupdf (PDF text extraction)
      - pdfplumber (PDF text extraction, fallback)

    All methods return empty string on failure — never None.
    """

    def __init__(self):
        self._tesseract_available: Optional[bool] = None
        self._pymupdf_available: Optional[bool] = None
        self._pdfplumber_available: Optional[bool] = None
        self._check_availability()
        logger.info("✅ DocumentExtractor initialized")

    def _check_availability(self):
        """Check which extraction backends are available."""
        # Check pytesseract
        try:
            import pytesseract
            # Verify Tesseract is actually installed
            try:
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
                logger.info("  pytesseract: available")
            except Exception:
                self._tesseract_available = False
                logger.warning(
                    "  pytesseract: installed but Tesseract engine not found. "
                    "Install from: https://github.com/UB-Mannheim/tesseract/wiki"
                )
        except ImportError:
            self._tesseract_available = False
            logger.debug("  pytesseract: not installed")

        # Check pymupdf
        try:
            import fitz  # pymupdf
            self._pymupdf_available = True
            logger.info("  pymupdf: available")
        except ImportError:
            self._pymupdf_available = False
            logger.debug("  pymupdf: not installed")

        # Check pdfplumber
        try:
            import pdfplumber
            self._pdfplumber_available = True
            logger.info("  pdfplumber: available")
        except ImportError:
            self._pdfplumber_available = False
            logger.debug("  pdfplumber: not installed")

        if not any([self._tesseract_available, self._pymupdf_available]):
            logger.warning(
                "No document extraction backends available. "
                "Install: pip install pytesseract pymupdf pdfplumber"
            )

    @property
    def is_available(self) -> bool:
        """Returns True if at least one extraction method is available."""
        return (
            self._tesseract_available
            or self._pymupdf_available
            or self._pdfplumber_available
        )

    # ── Image OCR ──────────────────────────────────────────

    def extract_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file using OCR.

        Args:
            image_path: Path to the image file (PNG, JPG, etc.).

        Returns:
            Extracted text, or empty string if extraction failed.
        """
        if not self._tesseract_available:
            logger.warning(
                "OCR not available (pytesseract/Tesseract not installed)"
            )
            return ""

        if not os.path.exists(image_path):
            logger.error("Image file not found: {}", image_path)
            return ""

        try:
            from PIL import Image
            import pytesseract

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            result = text.strip()
            logger.info(
                "OCR extracted {} chars from {}",
                len(result), os.path.basename(image_path),
            )
            return result
        except Exception as e:
            logger.error("Image OCR failed for '{}': {}", image_path, e)
            return ""

    def extract_from_image_bytes(self, image_data: bytes) -> str:
        """
        Extract text from raw image bytes.

        Args:
            image_data: Raw image file bytes (PNG, JPG, etc.).

        Returns:
            Extracted text, or empty string on failure.
        """
        if not self._tesseract_available:
            return ""

        try:
            from PIL import Image
            import pytesseract
            import io

            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)
            result = text.strip()
            logger.info("OCR extracted {} chars from image bytes", len(result))
            return result
        except Exception as e:
            logger.error("Image bytes OCR failed: {}", e)
            return ""

    # ── PDF Extraction ─────────────────────────────────────

    def extract_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file.

        Tries pymupdf first (faster), falls back to pdfplumber.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Extracted text, or empty string if extraction failed.
        """
        if not os.path.exists(pdf_path):
            logger.error("PDF file not found: {}", pdf_path)
            return ""

        # Try pymupdf first
        if self._pymupdf_available:
            result = self._extract_pdf_pymupdf(pdf_path)
            if result:
                return result

        # Fallback to pdfplumber
        if self._pdfplumber_available:
            result = self._extract_pdf_pdfplumber(pdf_path)
            if result:
                return result

        logger.warning("No PDF extraction backend available for '{}'", pdf_path)
        return ""

    def _extract_pdf_pymupdf(self, pdf_path: str) -> str:
        """Extract text using pymupdf (fastest)."""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text_parts = []
            for page_num, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    text_parts.append(text)
            doc.close()
            result = "\n\n".join(text_parts)
            logger.info(
                "pymupdf extracted {} chars from {} ({} pages)",
                len(result), os.path.basename(pdf_path), len(doc),
            )
            return result
        except Exception as e:
            logger.error("pymupdf extraction failed for '{}': {}", pdf_path, e)
            return ""

    def _extract_pdf_pdfplumber(self, pdf_path: str) -> str:
        """Extract text using pdfplumber (slower but more precise)."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(text.strip())
            result = "\n\n".join(text_parts)
            logger.info(
                "pdfplumber extracted {} chars from {} ({} pages)",
                len(result), os.path.basename(pdf_path), len(pdf.pages),
            )
            return result
        except Exception as e:
            logger.error(
                "pdfplumber extraction failed for '{}': {}", pdf_path, e
            )
            return ""

    # ── Utility ────────────────────────────────────────────

    def extract_from_path(self, file_path: str) -> str:
        """
        Auto-detect file type and extract text.

        Supports: images (PNG, JPG, JPEG, BMP, TIFF, WEBP) and PDFs.

        Args:
            file_path: Path to the file.

        Returns:
            Extracted text, or empty string on failure.
        """
        ext = Path(file_path).suffix.lower()

        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
            return self.extract_from_image(file_path)
        elif ext == ".pdf":
            return self.extract_from_pdf(file_path)
        else:
            logger.warning("Unsupported file type '{}' for '{}'", ext, file_path)
            return ""

    def summarize_extracted(self, text: str, max_length: int = 500) -> str:
        """
        Summarize extracted text by taking the first meaningful portion.

        This is a simple extractive summarization. For AI-powered
        summarization, pass the text through the AI router.

        Args:
            text: The extracted text content.
            max_length: Maximum length of the summary.

        Returns:
            Summarized text.
        """
        if not text:
            return ""

        if len(text) <= max_length:
            return text

        # Try to break at a sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        break_point = max(last_period, last_newline)
        if break_point > max_length // 2:
            return text[:break_point + 1] + "..."

        return truncated + "..."

    def shutdown(self):
        """Clean up resources."""
        logger.info("DocumentExtractor shutdown")