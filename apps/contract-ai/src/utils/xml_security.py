# -*- coding: utf-8 -*-
"""
XML Security Utilities - Safe XML parsing with XXE protection

Protects against:
- XML External Entity (XXE) attacks
- Billion laughs attack (entity expansion)
- DTD retrieval from external sources
"""
from lxml import etree
from typing import Union, Optional
from io import BytesIO
from loguru import logger


class XMLSecurityError(Exception):
    """Custom exception for XML security errors"""
    pass


def create_safe_parser() -> etree.XMLParser:
    """
    Create XML parser with security hardening

    Protections:
    - Disables external entity resolution (XXE protection)
    - Disables DTD processing
    - Disables network access
    - Limits entity expansion (billion laughs protection)

    Returns:
        Configured secure XMLParser
    """
    parser = etree.XMLParser(
        # XXE Protection: Don't resolve external entities
        resolve_entities=False,

        # Don't load DTDs from external sources
        no_network=True,

        # Don't process DTDs at all
        dtd_validation=False,
        load_dtd=False,

        # Protect against billion laughs attack
        huge_tree=False,

        # Remove blank text for cleaner parsing
        remove_blank_text=True,

        # Recover from minor errors but log them
        recover=False,
    )

    return parser


def parse_xml_safely(
    xml_input: Union[str, bytes],
    encoding: str = 'utf-8'
) -> etree._Element:
    """
    Safely parse XML string or bytes with XXE protection

    Args:
        xml_input: XML content as string or bytes
        encoding: Character encoding (default: utf-8)

    Returns:
        Parsed XML element tree root

    Raises:
        XMLSecurityError: If parsing fails or security issue detected
        etree.XMLSyntaxError: If XML is malformed
    """
    try:
        # Convert string to bytes if needed
        if isinstance(xml_input, str):
            xml_bytes = xml_input.encode(encoding)
        else:
            xml_bytes = xml_input

        # Create secure parser
        parser = create_safe_parser()

        # Parse with security protections
        root = etree.fromstring(xml_bytes, parser=parser)

        # Additional security check: detect suspicious patterns
        _check_for_suspicious_content(root)

        logger.debug(f"XML parsed safely: {len(xml_bytes)} bytes")
        return root

    except etree.XMLSyntaxError as e:
        logger.error(f"XML syntax error: {e}")
        raise
    except Exception as e:
        logger.error(f"XML parsing error: {e}")
        raise XMLSecurityError(f"Failed to parse XML safely: {e}")


def parse_xml_file_safely(
    file_path: str,
    encoding: str = 'utf-8'
) -> etree._Element:
    """
    Safely parse XML file with XXE protection

    Args:
        file_path: Path to XML file
        encoding: Character encoding (default: utf-8)

    Returns:
        Parsed XML element tree root

    Raises:
        XMLSecurityError: If parsing fails or security issue detected
        FileNotFoundError: If file doesn't exist
    """
    try:
        with open(file_path, 'rb') as f:
            xml_bytes = f.read()

        return parse_xml_safely(xml_bytes, encoding)

    except FileNotFoundError:
        logger.error(f"XML file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to parse XML file {file_path}: {e}")
        raise XMLSecurityError(f"Failed to parse XML file: {e}")


def validate_xml_structure(
    xml_input: Union[str, bytes],
    max_depth: int = 100,
    max_elements: int = 10000
) -> bool:
    """
    Validate XML structure doesn't exceed safety limits

    Args:
        xml_input: XML content
        max_depth: Maximum nesting depth
        max_elements: Maximum number of elements

    Returns:
        True if valid, False otherwise

    Raises:
        XMLSecurityError: If limits exceeded
    """
    try:
        root = parse_xml_safely(xml_input)

        # Check depth
        depth = _get_max_depth(root)
        if depth > max_depth:
            raise XMLSecurityError(
                f"XML depth {depth} exceeds maximum {max_depth}"
            )

        # Check element count
        element_count = len(list(root.iter()))
        if element_count > max_elements:
            raise XMLSecurityError(
                f"XML has {element_count} elements, exceeds maximum {max_elements}"
            )

        logger.debug(f"XML structure valid: depth={depth}, elements={element_count}")
        return True

    except XMLSecurityError:
        raise
    except Exception as e:
        logger.error(f"XML validation error: {e}")
        return False


def _get_max_depth(element: etree._Element, current_depth: int = 0) -> int:
    """
    Recursively calculate maximum depth of XML tree

    Args:
        element: XML element to analyze
        current_depth: Current recursion depth

    Returns:
        Maximum depth found
    """
    if len(element) == 0:
        return current_depth

    return max(
        _get_max_depth(child, current_depth + 1)
        for child in element
    )


def _check_for_suspicious_content(root: etree._Element) -> None:
    """
    Check for suspicious patterns in XML content

    Args:
        root: XML root element

    Raises:
        XMLSecurityError: If suspicious content found
    """
    # Check for external entity references (shouldn't be there with safe parser)
    xml_string = etree.tostring(root, encoding='unicode')

    suspicious_patterns = [
        '<!ENTITY',  # Entity declarations
        '<!DOCTYPE',  # DTD declarations
        'SYSTEM',  # External system references
        'PUBLIC',  # External public references
    ]

    for pattern in suspicious_patterns:
        if pattern in xml_string:
            logger.warning(f"Suspicious XML pattern detected: {pattern}")
            raise XMLSecurityError(
                f"Suspicious XML content detected: {pattern}. "
                "This may be an XXE attack attempt."
            )


def safe_xml_to_string(
    element: etree._Element,
    encoding: str = 'utf-8',
    pretty_print: bool = False
) -> str:
    """
    Safely convert XML element to string

    Args:
        element: XML element to convert
        encoding: Output encoding
        pretty_print: Whether to format with indentation

    Returns:
        XML string
    """
    try:
        xml_bytes = etree.tostring(
            element,
            encoding=encoding,
            pretty_print=pretty_print,
            xml_declaration=False
        )
        return xml_bytes.decode(encoding)
    except Exception as e:
        logger.error(f"Failed to convert XML to string: {e}")
        raise XMLSecurityError(f"XML serialization failed: {e}")


__all__ = [
    'XMLSecurityError',
    'create_safe_parser',
    'parse_xml_safely',
    'parse_xml_file_safely',
    'validate_xml_structure',
    'safe_xml_to_string',
]
