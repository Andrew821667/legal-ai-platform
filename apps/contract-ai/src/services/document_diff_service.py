# -*- coding: utf-8 -*-
"""
Document Diff Service - Structural comparison of contract documents
Supports XML/XPath diff, text diff, and semantic analysis
"""
import difflib
from typing import Dict, Any, List, Tuple, Optional
from lxml import etree
from loguru import logger


class DocumentDiffService:
    """
    Service for comparing contract document versions

    Features:
    - Text-based diff (additions/deletions/modifications)
    - XML/XPath structural diff
    - Change classification (textual/structural/semantic/legal)
    - Change location tracking
    """

    def __init__(self):
        pass

    def compare_documents(
        self,
        old_xml: str,
        new_xml: str,
        mode: str = 'combined'
    ) -> List[Dict[str, Any]]:
        """
        Compare two XML documents and extract changes

        Args:
            old_xml: XML content of old version
            new_xml: XML content of new version
            mode: 'text', 'structural', or 'combined'

        Returns:
            List of change dictionaries
        """
        try:
            logger.info(f"Comparing documents (mode={mode})")

            changes = []

            if mode in ['text', 'combined']:
                text_changes = self._text_diff(old_xml, new_xml)
                changes.extend(text_changes)

            if mode in ['structural', 'combined']:
                structural_changes = self._structural_diff(old_xml, new_xml)
                changes.extend(structural_changes)

            # Deduplicate and merge changes
            changes = self._merge_changes(changes)

            logger.info(f"Found {len(changes)} changes")
            return changes

        except Exception as e:
            logger.error(f"Document comparison failed: {e}")
            raise

    def _text_diff(self, old_xml: str, new_xml: str) -> List[Dict[str, Any]]:
        """
        Perform text-based diff using difflib

        Returns changes with line numbers and content
        """
        try:
            old_lines = old_xml.splitlines()
            new_lines = new_xml.splitlines()

            differ = difflib.Differ()
            diff = list(differ.compare(old_lines, new_lines))

            changes = []
            line_num = 0

            for i, line in enumerate(diff):
                if line.startswith('- '):
                    # Deletion
                    changes.append({
                        'change_type': 'deletion',
                        'change_category': 'textual',
                        'line_number': line_num,
                        'old_content': line[2:],
                        'new_content': None
                    })
                elif line.startswith('+ '):
                    # Addition
                    changes.append({
                        'change_type': 'addition',
                        'change_category': 'textual',
                        'line_number': line_num,
                        'old_content': None,
                        'new_content': line[2:]
                    })
                elif line.startswith('? '):
                    # Skip marker lines
                    continue
                else:
                    # Unchanged line
                    line_num += 1

            return changes

        except Exception as e:
            logger.error(f"Text diff failed: {e}")
            return []

    def _structural_diff(self, old_xml: str, new_xml: str) -> List[Dict[str, Any]]:
        """
        Perform structural diff using XML/XPath

        Compares document structure element by element
        """
        try:
            # Parse XML
            old_tree = etree.fromstring(old_xml.encode('utf-8'))
            new_tree = etree.fromstring(new_xml.encode('utf-8'))

            changes = []

            # Get all elements with xpaths
            old_elements = self._get_all_elements_with_xpath(old_tree)
            new_elements = self._get_all_elements_with_xpath(new_tree)

            # Find deletions (in old but not in new)
            for xpath, old_elem in old_elements.items():
                if xpath not in new_elements:
                    changes.append({
                        'change_type': 'deletion',
                        'change_category': 'structural',
                        'xpath_location': xpath,
                        'section_name': self._extract_section_name(old_elem),
                        'old_content': self._element_to_text(old_elem),
                        'new_content': None
                    })

            # Find additions (in new but not in old)
            for xpath, new_elem in new_elements.items():
                if xpath not in old_elements:
                    changes.append({
                        'change_type': 'addition',
                        'change_category': 'structural',
                        'xpath_location': xpath,
                        'section_name': self._extract_section_name(new_elem),
                        'old_content': None,
                        'new_content': self._element_to_text(new_elem)
                    })

            # Find modifications (in both but content differs)
            for xpath in set(old_elements.keys()) & set(new_elements.keys()):
                old_elem = old_elements[xpath]
                new_elem = new_elements[xpath]

                old_text = self._element_to_text(old_elem)
                new_text = self._element_to_text(new_elem)

                if old_text != new_text:
                    changes.append({
                        'change_type': 'modification',
                        'change_category': 'structural',
                        'xpath_location': xpath,
                        'section_name': self._extract_section_name(old_elem),
                        'old_content': old_text,
                        'new_content': new_text
                    })

            return changes

        except Exception as e:
            logger.error(f"Structural diff failed: {e}")
            return []

    def _get_all_elements_with_xpath(self, tree: etree._Element) -> Dict[str, etree._Element]:
        """
        Get all elements in tree with their XPath locations

        Returns dict: {xpath: element}
        """
        elements = {}

        def traverse(elem, path=''):
            # Build xpath
            tag = elem.tag
            # Count preceding siblings with same tag
            siblings = list(elem.getparent()) if elem.getparent() is not None else [elem]
            index = sum(1 for s in siblings[:siblings.index(elem)] if s.tag == tag) + 1

            current_path = f"{path}/{tag}[{index}]" if path else f"/{tag}"

            # Store element
            elements[current_path] = elem

            # Recurse to children
            for child in elem:
                traverse(child, current_path)

        traverse(tree)
        return elements

    def _extract_section_name(self, elem: etree._Element) -> Optional[str]:
        """
        Extract section/clause name from element

        Looks for title, name, or id attributes
        """
        # Try common attributes
        for attr in ['title', 'name', 'id', 'section']:
            if attr in elem.attrib:
                return elem.attrib[attr]

        # Try finding child title element
        for child in elem:
            if 'title' in child.tag.lower():
                return child.text

        # Return tag name as fallback
        return elem.tag

    def _element_to_text(self, elem: etree._Element) -> str:
        """
        Extract text content from element and all children
        """
        return ''.join(elem.itertext()).strip()

    def _merge_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge duplicate changes from different diff methods

        Combines text and structural changes at same location
        """
        # Group by location (xpath or line number)
        grouped = {}

        for change in changes:
            # Create key for grouping
            if 'xpath_location' in change and change['xpath_location']:
                key = f"xpath:{change['xpath_location']}"
            elif 'line_number' in change:
                key = f"line:{change['line_number']}"
            else:
                # Unique change
                key = f"unique:{id(change)}"

            if key not in grouped:
                grouped[key] = change
            else:
                # Merge with existing
                existing = grouped[key]

                # Prefer structural category over textual
                if change['change_category'] == 'structural':
                    existing['change_category'] = 'structural'

                # Merge xpath if missing
                if 'xpath_location' in change and not existing.get('xpath_location'):
                    existing['xpath_location'] = change['xpath_location']

                # Merge section name if missing
                if 'section_name' in change and not existing.get('section_name'):
                    existing['section_name'] = change['section_name']

        return list(grouped.values())

    def classify_change_category(self, change: Dict[str, Any]) -> str:
        """
        Classify change into category: textual/structural/semantic/legal

        This is a heuristic classification - LLM will refine it later
        """
        old_content = change.get('old_content', '') or ''
        new_content = change.get('new_content', '') or ''

        # Keywords that indicate legal changes
        legal_keywords = [
            'обязан', 'должен', 'вправе', 'ответственност', 'штраф',
            'пеня', 'договор', 'срок', 'сумм', 'оплат', 'цен',
            'расторжен', 'закон', 'кодекс', 'статья'
        ]

        # Check for legal keywords
        combined = old_content.lower() + ' ' + new_content.lower()
        if any(keyword in combined for keyword in legal_keywords):
            return 'legal'

        # Check if structural (tags, sections)
        if '<' in old_content or '<' in new_content:
            return 'structural'

        # Check for semantic change (significant rewording)
        if old_content and new_content:
            similarity = self._text_similarity(old_content, new_content)
            if similarity < 0.5:  # Significant change
                return 'semantic'

        # Default to textual
        return 'textual'

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts (0.0-1.0)

        Uses SequenceMatcher from difflib
        """
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def extract_clause_number(self, content: str, xpath: Optional[str] = None) -> Optional[str]:
        """
        Extract clause/section number from content or xpath

        Examples: "5.2.3", "Clause 7", "Раздел 3"
        """
        import re

        # Try xpath first
        if xpath:
            # Look for patterns like section[5]/clause[2]
            match = re.search(r'section\[(\d+)\].*?clause\[(\d+)\]', xpath)
            if match:
                return f"{match.group(1)}.{match.group(2)}"

        # Try content
        if content:
            # Look for patterns like "5.2.3" or "п. 5.2"
            patterns = [
                r'(\d+\.)+\d+',  # 5.2.3
                r'п\.\s*(\d+\.?\d*)',  # п. 5.2
                r'раздел\s+(\d+)',  # раздел 3
                r'clause\s+(\d+)',  # clause 7
            ]

            for pattern in patterns:
                match = re.search(pattern, content.lower())
                if match:
                    return match.group(1) if match.lastindex == 1 else match.group(0)

        return None


__all__ = ["DocumentDiffService"]
