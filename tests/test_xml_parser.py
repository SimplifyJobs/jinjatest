"""Tests for XML parser module."""

import pytest

from jinjatest.parsers.xml_parser import XMLElement, XMLParseError, parse_xml


class TestParseXml:
    """Tests for parse_xml function."""

    def test_parse_simple_element(self):
        result = parse_xml("<root>content</root>")
        assert isinstance(result, XMLElement)
        assert result.tag == "root"
        assert result.text == "content"

    def test_parse_element_with_attributes(self):
        result = parse_xml('<item id="1" name="test">value</item>')
        assert result.tag == "item"
        assert result.attrib == {"id": "1", "name": "test"}
        assert result.text == "value"

    def test_parse_nested_elements(self):
        xml = """
        <parent>
            <child1>one</child1>
            <child2>two</child2>
        </parent>
        """
        result = parse_xml(xml)
        assert result.tag == "parent"
        assert len(result.children) == 2
        assert result.children[0].tag == "child1"
        assert result.children[0].text == "one"
        assert result.children[1].tag == "child2"
        assert result.children[1].text == "two"

    def test_parse_with_xml_declaration(self):
        xml = '<?xml version="1.0" encoding="UTF-8"?><root>content</root>'
        result = parse_xml(xml)
        assert result.tag == "root"
        assert result.text == "content"

    def test_parse_empty_raises_error(self):
        with pytest.raises(XMLParseError) as exc_info:
            parse_xml("")
        assert "Empty XML content" in str(exc_info.value)

    def test_parse_invalid_xml_raises_error(self):
        with pytest.raises(XMLParseError) as exc_info:
            parse_xml("<unclosed>")
        assert "Failed to parse" in str(exc_info.value)


class TestParseXmlFragments:
    """Tests for parsing XML-like fragments."""

    def test_parse_multiple_root_elements(self):
        xml = """
        <instructions>Do this</instructions>
        <context>Some context</context>
        """
        result = parse_xml(xml)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].tag == "instructions"
        assert result[0].text == "Do this"
        assert result[1].tag == "context"
        assert result[1].text == "Some context"

    def test_parse_fragment_returns_single_when_one_element(self):
        xml = "<single>element</single>"
        result = parse_xml(xml)
        assert isinstance(result, XMLElement)
        assert result.tag == "single"

    def test_parse_fragment_with_mixed_content(self):
        xml = """
        <step>First step</step>
        <step>Second step</step>
        <step>Third step</step>
        """
        result = parse_xml(xml)
        assert isinstance(result, list)
        assert len(result) == 3
        for i, elem in enumerate(result):
            assert elem.tag == "step"

    def test_strict_mode_rejects_fragments(self):
        xml = "<a>one</a><b>two</b>"
        with pytest.raises(XMLParseError):
            parse_xml(xml, strict=True)

    def test_strict_mode_accepts_valid_xml(self):
        xml = "<root><a>one</a><b>two</b></root>"
        result = parse_xml(xml, strict=True)
        assert result.tag == "root"
        assert len(result.children) == 2


class TestXMLElement:
    """Tests for XMLElement class."""

    def test_find_child(self):
        result = parse_xml("<root><a>1</a><b>2</b></root>")
        child = result.find("a")
        assert child is not None
        assert child.text == "1"

    def test_find_returns_none_when_not_found(self):
        result = parse_xml("<root><a>1</a></root>")
        assert result.find("missing") is None

    def test_find_all_children(self):
        result = parse_xml("<root><item>1</item><item>2</item><other>3</other></root>")
        items = result.find_all("item")
        assert len(items) == 2
        assert items[0].text == "1"
        assert items[1].text == "2"

    def test_to_dict_basic(self):
        result = parse_xml("<root>content</root>")
        d = result.to_dict()
        assert d == {"#text": "content"}

    def test_to_dict_with_attributes(self):
        result = parse_xml('<item id="1">value</item>')
        d = result.to_dict()
        assert d == {"@id": "1", "#text": "value"}

    def test_to_dict_with_children(self):
        result = parse_xml("<root><a>1</a><b>2</b></root>")
        d = result.to_dict()
        assert d == {"a": {"#text": "1"}, "b": {"#text": "2"}}

    def test_to_dict_multiple_same_children(self):
        result = parse_xml("<root><item>1</item><item>2</item></root>")
        d = result.to_dict()
        assert d == {"item": [{"#text": "1"}, {"#text": "2"}]}

    def test_get_text_simple(self):
        result = parse_xml("<root>simple text</root>")
        assert result.get_text() == "simple text"

    def test_get_text_with_children(self):
        result = parse_xml("<root>Hello <b>world</b>!</root>")
        # The text content is extracted from all nested elements
        text = result.get_text()
        assert "Hello" in text
        assert "world" in text


class TestXMLParseError:
    """Tests for XMLParseError."""

    def test_error_message(self):
        err = XMLParseError("Test error")
        assert str(err) == "Test error"
        assert err.original_error is None

    def test_error_with_original(self):
        original = ValueError("original")
        err = XMLParseError("Test error", original_error=original)
        assert err.original_error is original
