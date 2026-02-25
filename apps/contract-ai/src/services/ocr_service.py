# -*- coding: utf-8 -*-
"""
OCR Service - Optical Character Recognition for scanned documents

Поддержка извлечения текста из:
- Сканированных PDF
- Изображений (PNG, JPEG, TIFF)
"""
import os
import tempfile
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger


class OCRService:
    """
    OCR service using Tesseract for text extraction from images

    Dependencies:
    - pytesseract (Python wrapper for Tesseract)
    - pdf2image (PDF to PIL Image conversion)
    - Pillow (Image processing)
    - tesseract (system binary)

    Install:
    pip install pytesseract pdf2image Pillow

    System requirements:
    - Ubuntu/Debian: apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils
    - macOS: brew install tesseract tesseract-lang poppler
    - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
    """

    def __init__(self, language: str = 'rus+eng', dpi: int = 300):
        """
        Initialize OCR service

        Args:
            language: Tesseract language(s) (e.g., 'rus', 'eng', 'rus+eng')
            dpi: DPI for PDF rendering (higher = better quality, slower)
        """
        self.language = language
        self.dpi = dpi
        self._check_dependencies()

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            from PIL import Image

            # Check tesseract binary
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"✓ Tesseract OCR found: {version}")
                return True
            except Exception as e:
                logger.warning(f"⚠ Tesseract OCR not found: {e}")
                logger.warning("Install: apt-get install tesseract-ocr tesseract-ocr-rus")
                return False

        except ImportError as e:
            logger.warning(f"⚠ OCR dependencies not installed: {e}")
            logger.warning("Install: pip install pytesseract pdf2image Pillow")
            return False

    def extract_text_from_pdf(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> str:
        """
        Extract text from scanned PDF using OCR

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to process (None = all pages)

        Returns:
            Extracted text

        Raises:
            FileNotFoundError: If PDF not found
            ImportError: If dependencies not installed
            RuntimeError: If OCR fails
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            import pytesseract
            from pdf2image import convert_from_path

            logger.info(f"Starting OCR extraction from PDF: {pdf_path}")

            # Convert PDF to images
            logger.info(f"Converting PDF to images (DPI: {self.dpi})...")
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt='jpeg',
                thread_count=2,  # Parallel conversion
                last_page=max_pages
            )

            total_pages = len(images)
            logger.info(f"✓ Converted {total_pages} pages to images")

            # Extract text from each page
            extracted_text = []

            for i, image in enumerate(images, 1):
                logger.info(f"Processing page {i}/{total_pages}...")

                try:
                    # Run OCR on image
                    text = pytesseract.image_to_string(
                        image,
                        lang=self.language,
                        config='--psm 1 --oem 3'  # PSM 1 = Automatic page segmentation with OSD
                    )

                    # Clean up text
                    text = self._clean_ocr_text(text)

                    if text.strip():
                        extracted_text.append(f"\n--- Page {i} ---\n")
                        extracted_text.append(text)
                        logger.info(f"✓ Page {i}: extracted {len(text)} characters")
                    else:
                        logger.warning(f"⚠ Page {i}: no text extracted")

                except Exception as e:
                    logger.error(f"✗ Page {i} OCR failed: {e}")
                    extracted_text.append(f"\n--- Page {i} [OCR FAILED] ---\n")

            full_text = '\n'.join(extracted_text)
            logger.info(f"✓ OCR extraction complete: {len(full_text)} total characters")

            return full_text

        except ImportError as e:
            logger.error(f"OCR dependencies not available: {e}")
            raise ImportError(
                "OCR requires: pip install pytesseract pdf2image Pillow\n"
                "System: apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils"
            )
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise RuntimeError(f"OCR failed: {e}")

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from image using OCR

        Args:
            image_path: Path to image (PNG, JPEG, TIFF, etc.)

        Returns:
            Extracted text
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            import pytesseract
            from PIL import Image

            logger.info(f"Starting OCR extraction from image: {image_path}")

            # Open image
            image = Image.open(image_path)

            # Run OCR
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config='--psm 1 --oem 3'
            )

            # Clean up
            text = self._clean_ocr_text(text)

            logger.info(f"✓ OCR extraction complete: {len(text)} characters")
            return text

        except ImportError as e:
            raise ImportError(
                "OCR requires: pip install pytesseract Pillow\n"
                "System: apt-get install tesseract-ocr tesseract-ocr-rus"
            )
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise RuntimeError(f"OCR failed: {e}")

    def detect_if_scanned(self, pdf_path: str, threshold: int = 100) -> Tuple[bool, str]:
        """
        Detect if PDF is scanned (image-based) or text-based

        Strategy:
        - Try extracting text with standard PDF parser
        - If text length < threshold, likely scanned

        Args:
            pdf_path: Path to PDF
            threshold: Minimum text length for text-based PDF

        Returns:
            (is_scanned, reason)
        """
        try:
            import PyPDF2

            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)

                # Check first 3 pages
                text_length = 0
                pages_checked = min(3, len(pdf_reader.pages))

                for i in range(pages_checked):
                    page = pdf_reader.pages[i]
                    text = page.extract_text()
                    text_length += len(text.strip())

                avg_length = text_length / pages_checked if pages_checked > 0 else 0

                if avg_length < threshold:
                    return (True, f"Low text content: {avg_length:.0f} chars/page < {threshold}")
                else:
                    return (False, f"Text-based PDF: {avg_length:.0f} chars/page")

        except Exception as e:
            logger.warning(f"Could not detect PDF type: {e}")
            return (True, "Detection failed, assuming scanned")

    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean OCR artifacts and improve text quality

        Common OCR errors:
        - Extra whitespace
        - Broken words
        - Encoding issues
        """
        # Remove excessive whitespace
        import re

        # Normalize line breaks
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')

        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)

        # Remove multiple line breaks
        text = re.sub(r'\n\n+', '\n\n', text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def get_supported_languages(self) -> List[str]:
        """
        Get list of installed Tesseract languages

        Returns:
            List of language codes
        """
        try:
            import pytesseract
            langs = pytesseract.get_languages()
            logger.info(f"Installed Tesseract languages: {langs}")
            return langs
        except Exception as e:
            logger.error(f"Could not get languages: {e}")
            return []


__all__ = ['OCRService']
