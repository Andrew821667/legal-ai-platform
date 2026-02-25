# -*- coding: utf-8 -*-
"""
Clause Extractor - Extract and structure contract clauses from XML

Извлекает пункты договора из XML для дальнейшего анализа
"""
from typing import Dict, Any, List
from loguru import logger
from lxml import etree

from ..utils.xml_security import parse_xml_safely, XMLSecurityError


class ClauseExtractor:
    """
    Extracts contract clauses from XML documents

    Supports multiple XML formats:
    - DocumentParser format (<clauses><clause>)
    - Generic XML structure
    - Recursive extraction with depth tracking
    """

    @staticmethod
    def extract_structure(xml_content: str) -> Dict[str, Any]:
        """
        Extract high-level contract structure

        Args:
            xml_content: Raw XML content

        Returns:
            Structure dict with parties, price, terms, sections
        """
        try:
            tree = parse_xml_safely(xml_content)
            root = tree

            structure = {
                'sections': [],
                'parties': [],
                'price_info': {},
                'term_info': {},
                'payment_terms': [],
                'liability_clauses': [],
                'dispute_resolution': {}
            }

            # Extract parties
            parties = root.findall('.//party')
            for party in parties:
                party_info = {
                    'role': party.get('role', 'unknown'),
                    'name': party.findtext('name', ''),
                    'inn': party.findtext('inn', ''),
                    'xpath': f'//{party.tag}[@role="{party.get("role", "")}"]'
                }
                structure['parties'].append(party_info)

            # Extract price info
            price_elem = root.find('.//price')
            if price_elem is not None:
                structure['price_info'] = {
                    'amount': price_elem.findtext('amount', ''),
                    'currency': price_elem.findtext('currency', 'RUB'),
                    'xpath': f'//{price_elem.tag}'
                }

            # Extract term info
            term_elem = root.find('.//term')
            if term_elem is not None:
                structure['term_info'] = {
                    'start': term_elem.findtext('start', ''),
                    'end': term_elem.findtext('end', ''),
                    'xpath': f'//{term_elem.tag}'
                }

            # Extract all sections with detailed info
            for elem in root.iter():
                if elem.tag not in ['contract', 'party', 'price', 'term']:
                    text_content = elem.text or ''
                    full_text = ''.join(elem.itertext()).strip()

                    structure['sections'].append({
                        'tag': elem.tag,
                        'text': text_content,
                        'full_text': full_text,
                        'xpath': f'//{elem.tag}',
                        'attributes': dict(elem.attrib)
                    })

            return structure

        except Exception as e:
            logger.error(f"Structure extraction failed: {e}")
            return {}

    @staticmethod
    def extract_clauses(xml_content: str, max_clauses: int = 50) -> List[Dict[str, Any]]:
        """
        Extract individual contract clauses for analysis

        Args:
            xml_content: Raw XML content
            max_clauses: Maximum number of clauses to extract

        Returns:
            List of clause dicts with id, text, type, xpath
        """
        try:
            logger.info("Starting clause extraction from XML...")
            tree = parse_xml_safely(xml_content)
            root = tree

            logger.info(f"Root tag: {root.tag}, children: {len(list(root))}")

            clauses: List[Dict[str, Any]] = []
            clause_counter = 1

            def extract_recursive(element: etree._Element, parent_path: str = "", level: int = 0) -> None:
                """Recursive clause extraction"""
                nonlocal clause_counter

                # Skip root elements
                if level == 0 and element.tag in ['contract', 'document', 'root']:
                    logger.info(f"Processing root element: {element.tag}")
                    for child in element:
                        extract_recursive(child, element.tag, level + 1)
                    return

                # Get element text
                elem_text = (element.text or '').strip()
                full_text = ''.join(element.itertext()).strip()

                # Determine clause type
                clause_type = ClauseExtractor._determine_clause_type(element.tag, full_text)

                # Build path
                current_path = f"{parent_path}/{element.tag}" if parent_path else element.tag

                # Extract clause if has meaningful text (>5 chars)
                if full_text and len(full_text) > 5:
                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': element.tag,
                        'path': current_path,
                        'xpath': current_path,
                        'title': ClauseExtractor._extract_clause_title(element.tag, full_text),
                        'text': full_text[:2000],  # Limit to 2000 chars
                        'type': clause_type,
                        'level': level,
                        'attributes': dict(element.attrib),
                        'children_count': len(list(element))
                    }
                    clauses.append(clause)
                    logger.debug(f"Clause {clause_counter}: {element.tag} - {full_text[:50]}")
                    clause_counter += 1

                    # Don't recurse if no children
                    if len(list(element)) == 0:
                        return

                # Recurse into children
                for child in element:
                    extract_recursive(child, current_path, level + 1)

            extract_recursive(root)

            logger.info(f"✓ Extracted {len(clauses)} contract clauses")

            # Fallback to alternative method if no clauses found
            if len(clauses) == 0:
                logger.warning("No clauses found, trying alternative method...")
                clauses = ClauseExtractor._extract_clauses_alternative(xml_content)
                logger.info(f"Alternative method found {len(clauses)} clauses")

            return clauses[:max_clauses]

        except Exception as e:
            logger.error(f"Clause extraction failed: {e}")
            return []

    @staticmethod
    def _extract_clauses_alternative(xml_content: str) -> List[Dict[str, Any]]:
        """
        Alternative extraction for DocumentParser format

        Handles <clauses><clause> structure specifically
        """
        try:
            tree = parse_xml_safely(xml_content)
            clauses: List[Dict[str, Any]] = []

            # Try DocumentParser <clauses> container first
            clauses_container = tree.find('.//clauses')
            if clauses_container is not None:
                logger.info("Found <clauses> container from DocumentParser")
                clause_elements = clauses_container.findall('clause')
                logger.info(f"Found {len(clause_elements)} clause elements")

                for idx, clause_elem in enumerate(clause_elements, 1):
                    title_elem = clause_elem.find('title')
                    content_elem = clause_elem.find('content')

                    title = title_elem.text if title_elem is not None and title_elem.text else f"Пункт {idx}"

                    # Collect text from content
                    if content_elem is not None:
                        paragraphs = content_elem.findall('paragraph')
                        full_text = '\n'.join([p.text for p in paragraphs if p.text])
                    else:
                        full_text = ''.join(clause_elem.itertext()).strip()

                    if full_text and len(full_text) > 10:
                        clause = {
                            'id': clause_elem.get('id', f"clause_{idx}"),
                            'number': idx,
                            'tag': 'clause',
                            'path': f"/clauses/clause[{idx}]",
                            'xpath': f"/clauses/clause[{idx}]",
                            'title': title,
                            'text': full_text[:2000],
                            'type': clause_elem.get('type', ClauseExtractor._determine_clause_type(title, full_text)),
                            'level': 0,
                            'attributes': dict(clause_elem.attrib),
                            'children_count': len(list(clause_elem))
                        }
                        clauses.append(clause)
                        logger.info(f"✓ Extracted clause {idx}: {title[:50]}")

                if len(clauses) > 0:
                    logger.info(f"✅ Extracted {len(clauses)} clauses from DocumentParser format")
                    return clauses[:50]

            # Fallback: extract all elements with text
            logger.info("No <clauses> found, trying generic extraction...")
            all_elements = list(tree.iter())
            logger.info(f"Found {len(all_elements)} total XML elements")

            clause_counter = 1
            for elem in all_elements:
                full_text = ''.join(elem.itertext()).strip()

                if full_text and len(full_text) > 10:
                    # Skip if text matches parent (avoid duplicates)
                    parent = elem.getparent()
                    if parent is not None:
                        parent_text = ''.join(parent.itertext()).strip()
                        if full_text == parent_text:
                            continue

                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': elem.tag,
                        'path': f"/{elem.tag}",
                        'xpath': f"/{elem.tag}",
                        'title': ClauseExtractor._extract_clause_title(elem.tag, full_text),
                        'text': full_text[:2000],
                        'type': ClauseExtractor._determine_clause_type(elem.tag, full_text),
                        'level': 0,
                        'attributes': dict(elem.attrib),
                        'children_count': len(list(elem))
                    }
                    clauses.append(clause)
                    clause_counter += 1

            return clauses[:50]

        except Exception as e:
            logger.error(f"Alternative extraction failed: {e}")
            return []

    @staticmethod
    def _determine_clause_type(tag: str, text: str) -> str:
        """Determine clause type from tag and text"""
        tag_lower = tag.lower()
        text_lower = text.lower()

        # Type detection keywords
        type_keywords = {
            'financial': ['оплат', 'цена', 'стоимость', 'price', 'payment', 'деньги', 'руб'],
            'temporal': ['срок', 'дата', 'период', 'term', 'deadline', 'период'],
            'liability': ['ответств', 'штраф', 'пен', 'liability', 'penalty', 'санкц'],
            'termination': ['расторж', 'прекращ', 'termination', 'расторгнут'],
            'confidentiality': ['конфиденц', 'тайн', 'confidential', 'секрет'],
            'dispute_resolution': ['спор', 'арбитраж', 'dispute', 'суд', 'разреш'],
            'force_majeure': ['форс-мажор', 'непреодол', 'force majeure', 'обстоят'],
            'warranties': ['гарант', 'заверен', 'warranty', 'guarantee'],
            'intellectual_property': ['интеллектуальн', 'авторск', 'intellectual', 'copyright', 'патент'],
            'definitions': ['определен', 'термин', 'definition', 'понятия']
        }

        # Check tag first
        for clause_type, keywords in type_keywords.items():
            if any(kw in tag_lower for kw in keywords):
                return clause_type

        # Check text content
        for clause_type, keywords in type_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return clause_type

        return 'general'

    @staticmethod
    def _extract_clause_title(tag: str, text: str) -> str:
        """Extract clause title from tag or text"""
        # First try to use tag as title
        if tag and tag != 'clause':
            return tag.replace('_', ' ').title()

        # Extract first sentence or up to 50 chars
        first_sentence = text.split('.')[0].strip()
        if len(first_sentence) <= 50:
            return first_sentence

        return text[:50] + '...'


__all__ = ['ClauseExtractor']
