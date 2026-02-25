# -*- coding: utf-8 -*-
"""
Tracked Changes Parser - Extract tracked changes from DOCX files
Parses insertions, deletions, and formatting changes

DOCX tracked changes are stored in word/document.xml as:
- <w:ins> - insertions
- <w:del> - deletions
- <w:moveFrom> / <w:moveTo> - moved content
- Attributes: w:author, w:date, w:id
"""
import zipfile
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from lxml import etree
from loguru import logger


class TrackedChangesParser:
    """
    Parser for DOCX tracked changes (revision marks)

    Features:
    - Extract insertions (w:ins)
    - Extract deletions (w:del)
    - Extract moves (w:moveFrom, w:moveTo)
    - Extract author and timestamp
    - Map to document structure

    Uses direct XML parsing of DOCX internal structure
    """

    # Word XML namespaces
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }

    def __init__(self):
        pass

    def parse_tracked_changes(self, docx_path: str) -> List[Dict[str, Any]]:
        """
        Parse tracked changes from DOCX file

        Extracts:
        - Insertions (w:ins)
        - Deletions (w:del)
        - Moves (w:moveFrom, w:moveTo)
        - Author, date, ID for each change

        Args:
            docx_path: Path to DOCX file

        Returns:
            List of tracked changes with metadata
        """
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"DOCX file not found: {docx_path}")

        try:
            logger.info(f"Parsing tracked changes from {docx_path}")

            # Extract document.xml from DOCX
            document_xml = self._extract_document_xml(docx_path)

            if not document_xml:
                logger.warning("Could not extract document.xml from DOCX")
                return []

            # Parse XML
            root = etree.fromstring(document_xml.encode('utf-8'))

            # Find all tracked changes
            changes = []

            # 1. Find insertions (w:ins)
            insertions = root.findall('.//w:ins', namespaces=self.NAMESPACES)
            for ins in insertions:
                change = self._parse_insertion(ins)
                if change:
                    changes.append(change)

            # 2. Find deletions (w:del)
            deletions = root.findall('.//w:del', namespaces=self.NAMESPACES)
            for deletion in deletions:
                change = self._parse_deletion(deletion)
                if change:
                    changes.append(change)

            # 3. Find moves
            move_from = root.findall('.//w:moveFrom', namespaces=self.NAMESPACES)
            move_to = root.findall('.//w:moveTo', namespaces=self.NAMESPACES)

            for move in move_from:
                change = self._parse_move(move, 'moveFrom')
                if change:
                    changes.append(change)

            for move in move_to:
                change = self._parse_move(move, 'moveTo')
                if change:
                    changes.append(change)

            logger.info(f"✓ Found {len(changes)} tracked changes")
            return changes

        except Exception as e:
            logger.error(f"Failed to parse tracked changes: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_document_xml(self, docx_path: str) -> Optional[str]:
        """
        Extract word/document.xml from DOCX archive

        Args:
            docx_path: Path to DOCX file

        Returns:
            XML content as string or None
        """
        try:
            with zipfile.ZipFile(docx_path, 'r') as zip_ref:
                # Read document.xml
                with zip_ref.open('word/document.xml') as xml_file:
                    return xml_file.read().decode('utf-8')
        except Exception as e:
            logger.error(f"Could not extract document.xml: {e}")
            return None

    def _parse_insertion(self, ins_element: etree._Element) -> Optional[Dict[str, Any]]:
        """
        Parse insertion element (w:ins)

        Args:
            ins_element: <w:ins> element

        Returns:
            Change dictionary or None
        """
        try:
            change = {
                'type': 'insertion',
                'id': ins_element.get('{' + self.NAMESPACES['w'] + '}id'),
                'author': ins_element.get('{' + self.NAMESPACES['w'] + '}author'),
                'date': ins_element.get('{' + self.NAMESPACES['w'] + '}date'),
                'text': self._extract_text_from_element(ins_element)
            }

            return change

        except Exception as e:
            logger.error(f"Error parsing insertion: {e}")
            return None

    def _parse_deletion(self, del_element: etree._Element) -> Optional[Dict[str, Any]]:
        """
        Parse deletion element (w:del)

        Args:
            del_element: <w:del> element

        Returns:
            Change dictionary or None
        """
        try:
            change = {
                'type': 'deletion',
                'id': del_element.get('{' + self.NAMESPACES['w'] + '}id'),
                'author': del_element.get('{' + self.NAMESPACES['w'] + '}author'),
                'date': del_element.get('{' + self.NAMESPACES['w'] + '}date'),
                'text': self._extract_text_from_element(del_element)
            }

            return change

        except Exception as e:
            logger.error(f"Error parsing deletion: {e}")
            return None

    def _parse_move(self, move_element: etree._Element, move_type: str) -> Optional[Dict[str, Any]]:
        """
        Parse move element (w:moveFrom or w:moveTo)

        Args:
            move_element: <w:moveFrom> or <w:moveTo> element
            move_type: 'moveFrom' or 'moveTo'

        Returns:
            Change dictionary or None
        """
        try:
            change = {
                'type': move_type,
                'id': move_element.get('{' + self.NAMESPACES['w'] + '}id'),
                'author': move_element.get('{' + self.NAMESPACES['w'] + '}author'),
                'date': move_element.get('{' + self.NAMESPACES['w'] + '}date'),
                'text': self._extract_text_from_element(move_element)
            }

            return change

        except Exception as e:
            logger.error(f"Error parsing move: {e}")
            return None

    def _extract_text_from_element(self, element: etree._Element) -> str:
        """
        Extract text content from XML element

        Args:
            element: XML element

        Returns:
            Extracted text
        """
        # Find all <w:t> (text) elements
        text_elements = element.findall('.//w:t', namespaces=self.NAMESPACES)
        text_parts = [t.text for t in text_elements if t.text]
        return ''.join(text_parts)

    def has_tracked_changes(self, docx_path: str) -> bool:
        """
        Check if DOCX file contains tracked changes

        Args:
            docx_path: Path to DOCX file

        Returns:
            True if file has tracked changes
        """
        try:
            changes = self.parse_tracked_changes(docx_path)
            return len(changes) > 0
        except Exception as e:
            logger.error(f"Error checking for tracked changes: {e}")
            return False

    def generate_tracked_changes_docx(
        self,
        base_docx_path: str,
        changes: List[Dict[str, Any]],
        output_path: str,
        author: str = "Contract AI System"
    ) -> str:
        """
        Generate DOCX with tracked changes from change list

        Args:
            base_docx_path: Path to base DOCX
            changes: List of changes to apply as tracked changes
            output_path: Output file path
            author: Author name for tracked changes

        Returns:
            Path to generated file
        """
        try:
            logger.info(f"Generating DOCX with tracked changes: {output_path}")

            # Stub implementation
            # Real implementation would:
            # 1. Load base DOCX
            # 2. For each change, insert w:ins or w:del tags
            # 3. Set author and date
            # 4. Save to output_path

            logger.warning("[STUB] Tracked changes generation not fully implemented")
            logger.info(f"Would generate {len(changes)} tracked changes by {author}")

            # For stub, just copy base file
            import shutil
            shutil.copy(base_docx_path, output_path)

            return output_path

        except Exception as e:
            logger.error(f"Failed to generate tracked changes DOCX: {e}")
            raise


__all__ = ["TrackedChangesParser"]
