# -*- coding: utf-8 -*-
"""
Extended Document Parser - Support for all document formats
Formats: DOCX, DOC, PDF (with OCR), RTF, ODT, XML
"""
import os
from pathlib import Path
from typing import Optional
from loguru import logger

# Import original parser
from .document_parser import DocumentParser as BaseDocumentParser


class ExtendedDocumentParser(BaseDocumentParser):
    """
    Extended parser with support for:
    - DOCX/DOC (with tracked changes)
    - PDF (with OCR if needed)
    - RTF
    - ODT
    - XML (passthrough)
    """

    def __init__(self):
        super().__init__()
        self.supported_formats = ['.docx', '.doc', '.pdf', '.rtf', '.odt', '.xml']

    def parse(self, file_path: str, enable_ocr: bool = True) -> str:
        """
        Parse document to XML with auto-format detection

        Args:
            file_path: Path to document
            enable_ocr: Enable OCR for scanned PDFs

        Returns:
            XML string
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect file type
        ext = Path(file_path).suffix.lower()

        logger.info(f"Parsing {ext} document: {file_path}")

        if ext == '.xml':
            return self._parse_xml(file_path)
        elif ext in ['.docx', '.doc']:
            return self.parse_docx(file_path)  # Uses base class method
        elif ext == '.pdf':
            return self._parse_pdf_extended(file_path, enable_ocr)
        elif ext == '.rtf':
            return self._parse_rtf(file_path)
        elif ext == '.odt':
            return self._parse_odt(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def _parse_xml(self, file_path: str) -> str:
        """XML passthrough"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_pdf_extended(self, file_path: str, enable_ocr: bool) -> str:
        """
        Parse PDF with OCR support

        Strategy:
        1. Try standard PDF text extraction first (fast)
        2. If fails or low text content, use OCR (slow but works on scans)

        Note: OCR requires tesseract installed on system
        """
        try:
            # Try base parser first (fast for text-based PDFs)
            xml_content = self.parse_pdf(file_path)

            # Check if we got meaningful content
            if len(xml_content) > 200:  # Minimum reasonable content
                logger.info("✓ Text-based PDF parsed successfully")
                return xml_content

            # If content is too short, might be scanned
            if enable_ocr:
                logger.warning("PDF has low text content, trying OCR...")
                return self._parse_pdf_with_ocr(file_path)
            else:
                logger.warning("PDF has low text content but OCR disabled")
                return xml_content

        except Exception as e:
            if enable_ocr:
                logger.warning(f"Base PDF parser failed: {e}, trying OCR...")
                return self._parse_pdf_with_ocr(file_path)
            else:
                logger.error(f"PDF parsing failed and OCR disabled: {e}")
                raise

    def _parse_pdf_with_ocr(self, file_path: str) -> str:
        """
        Parse scanned PDF using OCR

        Args:
            file_path: Path to PDF

        Returns:
            XML string with extracted text
        """
        try:
            from .ocr_service import OCRService
            from lxml import etree

            logger.info(f"Starting OCR extraction for: {file_path}")

            # Initialize OCR service
            ocr = OCRService(language='rus+eng', dpi=300)

            # Check if PDF is scanned
            is_scanned, reason = ocr.detect_if_scanned(file_path)
            logger.info(f"PDF scan detection: {reason}")

            # Extract text with OCR
            text = ocr.extract_text_from_pdf(file_path, max_pages=None)

            if not text or len(text) < 50:
                logger.warning(f"OCR extracted minimal text ({len(text)} chars)")
                # Create minimal XML
                root = etree.Element("contract")
                content_elem = etree.SubElement(root, "content")
                content_elem.text = text or "No text extracted"

                xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)
                return xml_str

            # Convert extracted text to XML structure
            root = etree.Element("contract")
            metadata = etree.SubElement(root, "metadata")
            etree.SubElement(metadata, "source").text = "OCR"
            etree.SubElement(metadata, "original_file").text = os.path.basename(file_path)

            # Add content
            content = etree.SubElement(root, "content")

            # Split by page markers
            pages = text.split('--- Page ')
            for page_text in pages:
                if not page_text.strip():
                    continue

                # Extract page number if present
                lines = page_text.split('\n', 1)
                if len(lines) > 1:
                    page_elem = etree.SubElement(content, "page")
                    page_elem.text = lines[1].strip()
                else:
                    page_elem = etree.SubElement(content, "page")
                    page_elem.text = page_text.strip()

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            logger.info(f"✓ OCR completed: {len(text)} characters extracted")
            return xml_str

        except ImportError as e:
            logger.error(f"OCR dependencies not installed: {e}")
            logger.error("Install: pip install pytesseract pdf2image Pillow")
            logger.error("System: apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils")

            # Return minimal XML with error message
            from lxml import etree
            root = etree.Element("contract")
            error = etree.SubElement(root, "error")
            error.text = f"OCR not available: {str(e)}"

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)
            return xml_str

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise RuntimeError(f"OCR failed: {e}")

    def _parse_rtf(self, file_path: str) -> str:
        """
        Parse RTF to XML using striprtf library

        Returns properly formatted XML with contract content
        """
        logger.info(f"Parsing RTF: {file_path}")

        try:
            from striprtf.striprtf import rtf_to_text
            from lxml import etree

            # Read RTF file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                rtf_content = f.read()

            # Convert RTF to plain text
            text = rtf_to_text(rtf_content)

            # Convert to XML
            root = etree.Element("contract")
            content_elem = etree.SubElement(root, "content")
            content_elem.text = text.strip()

            # Add metadata
            meta_elem = etree.SubElement(root, "metadata")
            format_elem = etree.SubElement(meta_elem, "format")
            format_elem.text = "RTF"

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            logger.info(f"RTF parsed: {len(text)} characters")
            return xml_str

        except Exception as e:
            logger.error(f"RTF parsing error: {e}")
            # Fallback to basic extraction
            logger.warning("Falling back to basic RTF extraction")
            return self._parse_rtf_fallback(file_path)

    def _parse_rtf_fallback(self, file_path: str) -> str:
        """Fallback RTF parser using regex"""
        import re
        from lxml import etree

        with open(file_path, 'rb') as f:
            content = f.read().decode('latin-1', errors='ignore')

        # Remove RTF control words
        text = re.sub(r'\\[a-z]+\d*\s?', '', content)
        text = re.sub(r'[{}]', '', text)
        text = text.strip()

        root = etree.Element("contract")
        content_elem = etree.SubElement(root, "content")
        content_elem.text = text

        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)
        return xml_str

    def _parse_odt(self, file_path: str) -> str:
        """
        Parse ODT to XML using odfpy library

        Returns properly formatted XML with contract content
        """
        logger.info(f"Parsing ODT: {file_path}")

        try:
            from odf import text, teletype
            from odf.opendocument import load
            from lxml import etree

            # Load ODT document
            doc = load(file_path)

            # Extract all text
            all_paragraphs = doc.getElementsByType(text.P)
            text_content = []

            for paragraph in all_paragraphs:
                para_text = teletype.extractText(paragraph)
                if para_text.strip():
                    text_content.append(para_text)

            full_text = '\n'.join(text_content)

            # Convert to XML
            root = etree.Element("contract")
            content_elem = etree.SubElement(root, "content")
            content_elem.text = full_text.strip()

            # Add metadata
            meta_elem = etree.SubElement(root, "metadata")
            format_elem = etree.SubElement(meta_elem, "format")
            format_elem.text = "ODT"

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            logger.info(f"ODT parsed: {len(full_text)} characters")
            return xml_str

        except Exception as e:
            logger.error(f"ODT parsing error: {e}")
            raise


# Convenience function
def parse_document(file_path: str, enable_ocr: bool = True) -> str:
    """
    Parse any supported document format to XML

    Args:
        file_path: Path to document
        enable_ocr: Enable OCR for scanned PDFs

    Returns:
        XML string
    """
    parser = ExtendedDocumentParser()
    return parser.parse(file_path, enable_ocr=enable_ocr)


__all__ = ["ExtendedDocumentParser", "parse_document"]
