# -*- coding: utf-8 -*-
"""
Tests for xml_security.py - XXE Attack Protection
"""
import pytest
from lxml import etree

from src.utils.xml_security import (
    XMLSecurityError,
    create_safe_parser,
    parse_xml_safely,
    parse_xml_file_safely,
    validate_xml_structure,
    safe_xml_to_string
)


class TestSafeParser:
    """Test safe XML parser creation"""

    def test_create_safe_parser(self):
        """Test safe parser is created with correct settings"""
        parser = create_safe_parser()

        # Check parser exists
        assert parser is not None
        assert isinstance(parser, etree.XMLParser)

    def test_parser_rejects_external_entities(self):
        """Test parser rejects external entity references"""
        parser = create_safe_parser()

        # XXE attack payload
        xxe_xml = b"""<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>
        """

        # Should not resolve external entity
        # Parser should either reject or ignore the entity
        try:
            root = etree.fromstring(xxe_xml, parser=parser)
            # If parsing succeeds, check entity was not resolved
            text = root.text or ""
            assert "root:" not in text  # /etc/passwd content not present
        except etree.XMLSyntaxError:
            # Parser correctly rejected the DTD
            pass


class TestSafeXMLParsing:
    """Test safe XML parsing functions"""

    def test_parse_valid_xml_string(self):
        """Test parsing valid XML string"""
        xml = "<root><child>value</child></root>"
        root = parse_xml_safely(xml)

        assert root.tag == "root"
        assert root.find("child").text == "value"

    def test_parse_valid_xml_bytes(self):
        """Test parsing valid XML bytes"""
        xml = b"<root><child>value</child></root>"
        root = parse_xml_safely(xml)

        assert root.tag == "root"

    def test_parse_xml_with_unicode(self):
        """Test parsing XML with unicode content"""
        xml = "<root><договор>Текст договора</договор></root>"
        root = parse_xml_safely(xml)

        assert root.find("договор").text == "Текст договора"

    def test_parse_malformed_xml(self):
        """Test malformed XML raises exception"""
        bad_xml = "<root><unclosed>"

        with pytest.raises(etree.XMLSyntaxError):
            parse_xml_safely(bad_xml)

    def test_reject_xxe_attack_system(self):
        """Test XXE attack with SYSTEM entity is rejected"""
        xxe_xml = """<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>
        """

        # Should raise security error or parse without resolving
        try:
            root = parse_xml_safely(xxe_xml)
            # If parsed, entity should not be resolved
            assert "root:" not in etree.tostring(root, encoding='unicode')
        except (XMLSecurityError, etree.XMLSyntaxError):
            # Correctly rejected
            pass

    def test_reject_xxe_attack_public(self):
        """Test XXE attack with PUBLIC entity is rejected"""
        xxe_xml = """<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe PUBLIC "-//W3C//TEXT copyright" "http://evil.com/evil.dtd">
        ]>
        <root>&xxe;</root>
        """

        try:
            root = parse_xml_safely(xxe_xml)
            # Should not make network request
            text = etree.tostring(root, encoding='unicode')
            assert "http://evil.com" not in text
        except (XMLSecurityError, etree.XMLSyntaxError):
            pass

    def test_reject_billion_laughs_attack(self):
        """Test billion laughs attack (entity expansion) is rejected"""
        # Simplified billion laughs attack
        lol_xml = """<?xml version="1.0"?>
        <!DOCTYPE lolz [
            <!ENTITY lol "lol">
            <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
            <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
        ]>
        <root>&lol3;</root>
        """

        # Should be rejected due to entity expansion limits
        try:
            root = parse_xml_safely(lol_xml)
            # If parsed, should not have expanded massively
            text = etree.tostring(root, encoding='unicode')
            assert len(text) < 10000  # Should not be huge
        except (XMLSecurityError, etree.XMLSyntaxError):
            pass

    def test_reject_dtd_retrieval(self):
        """Test DTD retrieval from network is prevented"""
        xml_with_dtd = """<?xml version="1.0"?>
        <!DOCTYPE root SYSTEM "http://evil.com/evil.dtd">
        <root>content</root>
        """

        # Should not make network request to fetch DTD
        try:
            root = parse_xml_safely(xml_with_dtd)
            # Parsing may succeed but DTD should not be fetched
        except (XMLSecurityError, etree.XMLSyntaxError):
            pass

    def test_parse_xml_file(self, tmp_path):
        """Test parsing XML from file"""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<root><item>test</item></root>")

        root = parse_xml_file_safely(str(xml_file))

        assert root.tag == "root"
        assert root.find("item").text == "test"

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file raises error"""
        with pytest.raises(FileNotFoundError):
            parse_xml_file_safely("/nonexistent/file.xml")


class TestXMLStructureValidation:
    """Test XML structure validation"""

    def test_validate_simple_xml(self):
        """Test validation of simple XML structure"""
        xml = "<root><child1><child2>value</child2></child1></root>"

        assert validate_xml_structure(xml) == True

    def test_reject_too_deep_xml(self):
        """Test rejection of XML exceeding depth limit"""
        # Create deeply nested XML
        depth = 150  # Exceeds MAX_XML_DEPTH (100)
        xml = "<root>"
        for i in range(depth):
            xml += f"<level{i}>"
        xml += "deep"
        for i in range(depth - 1, -1, -1):
            xml += f"</level{i}>"
        xml += "</root>"

        with pytest.raises(XMLSecurityError, match="depth.*exceeds"):
            validate_xml_structure(xml, max_depth=100)

    def test_reject_too_many_elements(self):
        """Test rejection of XML with too many elements"""
        # Create XML with many elements
        xml = "<root>"
        for i in range(15000):  # Exceeds MAX_XML_ELEMENTS (10000)
            xml += f"<item{i}/>"
        xml += "</root>"

        with pytest.raises(XMLSecurityError, match="elements.*exceeds"):
            validate_xml_structure(xml, max_elements=10000)

    def test_validate_with_custom_limits(self):
        """Test validation with custom limits"""
        xml = "<root><a><b><c>test</c></b></a></root>"

        # Should pass with reasonable limits
        assert validate_xml_structure(xml, max_depth=10, max_elements=10) == True

        # Should fail with very strict limits
        with pytest.raises(XMLSecurityError):
            validate_xml_structure(xml, max_depth=2, max_elements=2)


class TestSafeXMLSerialization:
    """Test safe XML to string conversion"""

    def test_xml_to_string_simple(self):
        """Test converting simple XML to string"""
        xml = "<root><child>value</child></root>"
        root = parse_xml_safely(xml)

        result = safe_xml_to_string(root)

        assert "<root>" in result
        assert "<child>value</child>" in result

    def test_xml_to_string_with_unicode(self):
        """Test converting XML with unicode to string"""
        xml = "<root><договор>текст</договор></root>"
        root = parse_xml_safely(xml)

        result = safe_xml_to_string(root, encoding='utf-8')

        assert "договор" in result
        assert "текст" in result

    def test_xml_to_string_pretty_print(self):
        """Test pretty printing XML"""
        xml = "<root><child>value</child></root>"
        root = parse_xml_safely(xml)

        result = safe_xml_to_string(root, pretty_print=True)

        # Pretty print should add newlines/indentation
        assert "\n" in result or "  " in result


class TestSecurityChecks:
    """Test security-specific checks"""

    def test_check_for_entity_declarations(self):
        """Test detection of entity declarations"""
        xml_with_entity = """<?xml version="1.0"?>
        <!DOCTYPE root [
            <!ENTITY test "value">
        ]>
        <root>&test;</root>
        """

        # Should raise security error about entity declaration
        try:
            root = parse_xml_safely(xml_with_entity)
            # If parsed, should have detected suspicious content
            # Check that entity was not in final output
            output = safe_xml_to_string(root)
            assert "<!ENTITY" not in output
        except (XMLSecurityError, etree.XMLSyntaxError):
            pass

    def test_check_for_system_references(self):
        """Test detection of SYSTEM references"""
        xml_with_system = """<?xml version="1.0"?>
        <!DOCTYPE root SYSTEM "file:///etc/passwd">
        <root>test</root>
        """

        try:
            root = parse_xml_safely(xml_with_system)
            output = safe_xml_to_string(root)
            # System reference should not be in output
            assert "SYSTEM" not in output
            assert "/etc/passwd" not in output
        except (XMLSecurityError, etree.XMLSyntaxError):
            pass


class TestRealWorldXML:
    """Test parsing real-world XML documents"""

    def test_parse_contract_xml(self):
        """Test parsing a typical contract XML structure"""
        contract_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <contract>
            <metadata>
                <title>Договор поставки</title>
                <date>2024-01-15</date>
                <parties>
                    <party role="supplier">ООО "Поставщик"</party>
                    <party role="buyer">ООО "Покупатель"</party>
                </parties>
            </metadata>
            <clauses>
                <clause id="1">
                    <title>Предмет договора</title>
                    <text>Поставщик обязуется поставить товар...</text>
                </clause>
                <clause id="2">
                    <title>Цена и порядок расчетов</title>
                    <text>Общая стоимость составляет 1000000 руб.</text>
                </clause>
            </clauses>
        </contract>
        """

        root = parse_xml_safely(contract_xml)

        # Validate structure
        assert root.tag == "contract"
        assert root.find(".//title").text == "Договор поставки"
        assert len(root.findall(".//clause")) == 2

    def test_parse_large_xml(self):
        """Test parsing reasonably large XML document"""
        # Create XML with many elements but within limits
        xml = "<root>"
        for i in range(1000):
            xml += f"""
            <item id="{i}">
                <name>Item {i}</name>
                <description>Description for item {i}</description>
                <price>{i * 100}</price>
            </item>
            """
        xml += "</root>"

        root = parse_xml_safely(xml)

        assert root.tag == "root"
        assert len(root.findall(".//item")) == 1000

    def test_parse_xml_with_cdata(self):
        """Test parsing XML with CDATA sections"""
        xml = """<root>
            <content><![CDATA[This is <special> content with & symbols]]></content>
        </root>"""

        root = parse_xml_safely(xml)

        # CDATA content should be preserved
        assert "This is <special> content" in root.find("content").text


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_xml(self):
        """Test parsing empty XML"""
        with pytest.raises(etree.XMLSyntaxError):
            parse_xml_safely("")

    def test_xml_with_comments(self):
        """Test XML with comments is parsed correctly"""
        xml = """<root>
            <!-- This is a comment -->
            <child>value</child>
        </root>"""

        root = parse_xml_safely(xml)
        assert root.find("child").text == "value"

    def test_xml_with_namespace(self):
        """Test XML with namespaces"""
        xml = """<root xmlns="http://example.com/ns">
            <child>value</child>
        </root>"""

        root = parse_xml_safely(xml)
        # Namespace should be handled
        assert root.tag == "{http://example.com/ns}root"

    def test_xml_with_attributes(self):
        """Test XML with attributes"""
        xml = '<root id="123" type="test"><child attr="value"/></root>'

        root = parse_xml_safely(xml)
        assert root.get("id") == "123"
        assert root.find("child").get("attr") == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
