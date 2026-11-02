# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/document_analyzer.py  —  Document Analysis
#
#  Integrates document analysis into the assistant workflow.
#
#  Features:
#  - PDF text extraction and summarization
#  - Image OCR and text extraction
#  - Document drag-drop support
#  - Context-aware document Q&A
#  - Integration with memory system
#
#  Uses the existing DocumentExtractor utility and extends
#  it with assistant-specific features.
# ============================================================

import os
import threading
from typing import Callable, Optional
from pathlib import Path
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState


class DocumentAnalyzer:
    """
    Document analysis integration for the assistant.
    
    Provides document processing and analysis capabilities
    within the assistant workflow.
    
    Usage:
        analyzer = DocumentAnalyzer(state_engine)
        analyzer.set_ai_client(ai_client)
        
        # Analyze a document
        result = analyzer.analyze_file("document.pdf")
        
        # Ask questions about the document
        answer = analyzer.ask_about_document("What is the main topic?")
    """
    
    # Supported file types
    SUPPORTED_TYPES = {
        "pdf": [".pdf"],
        "image": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"],
        "text": [".txt", ".md", ".rst", ".log"],
        "code": [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs"],
        "document": [".doc", ".docx", ".rtf"],
    }
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # AI client for analysis
        self._ai_client = None
        
        # Current document context
        self._current_document: Optional[dict] = None
        self._document_text: str = ""
        self._document_summary: str = ""
        
        # Callbacks
        self._on_analysis_start: Optional[Callable] = None
        self._on_analysis_complete: Optional[Callable[[dict], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Configuration
        self._max_file_size = 50 * 1024 * 1024  # 50MB
        self._auto_summarize = True
        
        logger.debug("DocumentAnalyzer initialized")
    
    # ── Client Integration ────────────────────────────────────
    
    def set_ai_client(self, client):
        """Set the AI client for document analysis."""
        with self._lock:
            self._ai_client = client
            logger.debug("AI client set for document analysis")
    
    # ── Callback Registration ─────────────────────────────────
    
    def set_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_complete: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """Set analysis callbacks."""
        with self._lock:
            if on_start:
                self._on_analysis_start = on_start
            if on_complete:
                self._on_analysis_complete = on_complete
            if on_error:
                self._on_error = on_error
    
    # ── Document Analysis ─────────────────────────────────────
    
    def analyze_file(self, file_path: str) -> Optional[dict]:
        """
        Analyze a document file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dict with document info and extracted text, or None on error
        """
        with self._lock:
            path = Path(file_path)
            
            # Validate file
            if not path.exists():
                logger.error("File not found: {}", file_path)
                self._notify_error(f"File not found: {file_path}")
                return None
            
            if path.stat().st_size > self._max_file_size:
                logger.error("File too large: {}", file_path)
                self._notify_error("File is too large (max 50MB)")
                return None
            
            # Determine file type
            file_type = self._get_file_type(path)
            if not file_type:
                logger.error("Unsupported file type: {}", path.suffix)
                self._notify_error(f"Unsupported file type: {path.suffix}")
                return None
            
            logger.info("Analyzing document: {} ({})", path.name, file_type)
            
            # Notify start
            self.state_engine.state = AssistantState.EXECUTING
            if self._on_analysis_start:
                try:
                    self._on_analysis_start()
                except Exception as e:
                    logger.error("Start callback error: {}", e)
            
            # Extract text based on type
            try:
                text = self._extract_text(path, file_type)
                
                if not text:
                    self._notify_error("Could not extract text from document")
                    return None
                
                # Store document context
                result = {
                    "path": str(path),
                    "name": path.name,
                    "type": file_type,
                    "size": path.stat().st_size,
                    "text": text,
                    "text_length": len(text),
                    "word_count": len(text.split()),
                }
                
                self._current_document = result
                self._document_text = text
                
                # Auto-summarize if enabled
                if self._auto_summarize and self._ai_client:
                    self._generate_summary(text)
                    result["summary"] = self._document_summary
                
                # Notify complete
                if self._on_analysis_complete:
                    try:
                        self._on_analysis_complete(result)
                    except Exception as e:
                        logger.error("Complete callback error: {}", e)
                
                logger.info("Document analysis complete: {} words", result["word_count"])
                return result
                
            except Exception as e:
                logger.error("Analysis error: {}", e)
                self._notify_error(f"Analysis error: {e}")
                return None
            
            finally:
                if self.state_engine.state == AssistantState.EXECUTING:
                    self.state_engine.state = AssistantState.IDLE
    
    def analyze_file_async(self, file_path: str):
        """Analyze a document file asynchronously."""
        thread = threading.Thread(
            target=self.analyze_file,
            args=(file_path,),
            daemon=True,
            name="DocumentAnalyzer",
        )
        thread.start()
    
    def _get_file_type(self, path: Path) -> Optional[str]:
        """Determine file type from extension."""
        suffix = path.suffix.lower()
        
        for file_type, extensions in self.SUPPORTED_TYPES.items():
            if suffix in extensions:
                return file_type
        
        return None
    
    def _extract_text(self, path: Path, file_type: str) -> str:
        """Extract text from a file based on type."""
        if file_type == "text" or file_type == "code":
            return self._extract_text_file(path)
        elif file_type == "pdf":
            return self._extract_pdf(path)
        elif file_type == "image":
            return self._extract_image(path)
        elif file_type == "document":
            return self._extract_document(path)
        
        return ""
    
    def _extract_text_file(self, path: Path) -> str:
        """Extract text from a plain text file."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error("Text extraction error: {}", e)
            return ""
    
    def _extract_pdf(self, path: Path) -> str:
        """Extract text from a PDF file."""
        try:
            # Try using the existing DocumentExtractor
            from utils.document_extractor import DocumentExtractor
            extractor = DocumentExtractor()
            return extractor.extract_pdf(str(path))
        except ImportError:
            logger.warning("DocumentExtractor not available")
        
        # Fallback: try PyPDF2
        try:
            import PyPDF2
            text = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
            return "\n".join(text)
        except ImportError:
            logger.warning("PyPDF2 not available")
        except Exception as e:
            logger.error("PDF extraction error: {}", e)
        
        return ""
    
    def _extract_image(self, path: Path) -> str:
        """Extract text from an image using OCR."""
        try:
            # Try using the existing DocumentExtractor
            from utils.document_extractor import DocumentExtractor
            extractor = DocumentExtractor()
            return extractor.extract_image(str(path))
        except ImportError:
            logger.warning("DocumentExtractor not available")
        
        # Fallback: try pytesseract
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(path)
            return pytesseract.image_to_string(image)
        except ImportError:
            logger.warning("pytesseract not available")
        except Exception as e:
            logger.error("OCR error: {}", e)
        
        return ""
    
    def _extract_document(self, path: Path) -> str:
        """Extract text from a Word document."""
        try:
            import docx
            doc = docx.Document(str(path))
            text = []
            for para in doc.paragraphs:
                text.append(para.text)
            return "\n".join(text)
        except ImportError:
            logger.warning("python-docx not available")
        except Exception as e:
            logger.error("Document extraction error: {}", e)
        
        return ""
    
    # ── Summarization ─────────────────────────────────────────
    
    def _generate_summary(self, text: str):
        """Generate a summary of the document text."""
        if not self._ai_client:
            return
        
        # Truncate text if too long
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = f"""Please provide a concise summary of the following document. 
Include the main topics, key points, and any important details.

Document:
{text}

Summary:"""
        
        try:
            if hasattr(self._ai_client, 'generate'):
                response = self._ai_client.generate(prompt)
                self._document_summary = response
            elif hasattr(self._ai_client, 'chat'):
                response = self._ai_client.chat(prompt)
                self._document_summary = response
            else:
                logger.warning("AI client has no generate/chat method")
        except Exception as e:
            logger.error("Summary generation error: {}", e)
            self._document_summary = ""
    
    def get_summary(self) -> str:
        """Get the current document summary."""
        return self._document_summary
    
    # ── Document Q&A ──────────────────────────────────────────
    
    def ask_about_document(self, question: str) -> str:
        """
        Ask a question about the current document.
        
        Args:
            question: Question to ask about the document
            
        Returns:
            Answer from the AI, or error message
        """
        if not self._document_text:
            return "No document is currently loaded."
        
        if not self._ai_client:
            return "AI client not available."
        
        # Build context-aware prompt
        context = self._document_text[:8000]  # Limit context
        
        prompt = f"""Based on the following document, please answer the question.
If the answer cannot be found in the document, say so.

Document:
{context}

Question: {question}

Answer:"""
        
        try:
            if hasattr(self._ai_client, 'generate'):
                return self._ai_client.generate(prompt)
            elif hasattr(self._ai_client, 'chat'):
                return self._ai_client.chat(prompt)
            else:
                return "AI client has no generate method."
        except Exception as e:
            logger.error("Q&A error: {}", e)
            return f"Error answering question: {e}"
    
    # ── Document Context ──────────────────────────────────────
    
    def get_current_document(self) -> Optional[dict]:
        """Get the current document info."""
        return self._current_document
    
    def get_document_text(self) -> str:
        """Get the current document text."""
        return self._document_text
    
    def has_document(self) -> bool:
        """Check if a document is loaded."""
        return self._current_document is not None
    
    def clear_document(self):
        """Clear the current document context."""
        with self._lock:
            self._current_document = None
            self._document_text = ""
            self._document_summary = ""
            logger.debug("Document context cleared")
    
    # ── Configuration ─────────────────────────────────────────
    
    def set_max_file_size(self, bytes: int):
        """Set maximum file size for analysis."""
        self._max_file_size = max(1024 * 1024, bytes)  # Min 1MB
        logger.debug("Max file size: {} bytes", self._max_file_size)
    
    def set_auto_summarize(self, enabled: bool):
        """Enable/disable automatic summarization."""
        self._auto_summarize = enabled
        logger.debug("Auto-summarize: {}", enabled)
    
    def get_supported_types(self) -> list[str]:
        """Get list of supported file extensions."""
        extensions = []
        for exts in self.SUPPORTED_TYPES.values():
            extensions.extend(exts)
        return extensions
    
    # ── Utilities ─────────────────────────────────────────────
    
    def _notify_error(self, message: str):
        """Notify error callback."""
        if self._on_error:
            try:
                self._on_error(message)
            except Exception as e:
                logger.error("Error callback error: {}", e)
    
    def destroy(self):
        """Clean up and destroy the analyzer."""
        self.clear_document()
        logger.debug("DocumentAnalyzer destroyed")
    
    def __repr__(self) -> str:
        has_doc = self.has_document()
        return f"DocumentAnalyzer(has_document={has_doc})"