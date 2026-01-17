"""Tests for fenced code block extraction."""

import pytest

from jinjatest import TemplateSpec
from jinjatest.parsers.fenced_blocks import (
    FencedBlock,
    extract_fenced_blocks,
    parse_fenced_blocks,
)
from jinjatest.parsers.json_parser import parse_json


class TestExtractFencedBlocks:
    """Tests for extract_fenced_blocks function."""

    def test_extract_single_json_block(self):
        text = """
Some text before
```json
{"key": "value"}
```
Some text after
"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "json"
        assert blocks[0].content == '{"key": "value"}'

    def test_extract_multiple_blocks(self):
        text = """
```json
{"first": 1}
```
Some text
```yaml
key: value
```
More text
```json
{"second": 2}
```
"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 3
        assert blocks[0].language == "json"
        assert blocks[1].language == "yaml"
        assert blocks[2].language == "json"

    def test_filter_by_language(self):
        text = """
```json
{"data": 1}
```
```yaml
key: value
```
```json
{"data": 2}
```
"""
        json_blocks = extract_fenced_blocks(text, language="json")
        assert len(json_blocks) == 2
        assert all(b.language == "json" for b in json_blocks)

        yaml_blocks = extract_fenced_blocks(text, language="yaml")
        assert len(yaml_blocks) == 1
        assert yaml_blocks[0].language == "yaml"

    def test_language_filter_case_insensitive(self):
        text = """
```JSON
{"key": "value"}
```
"""
        blocks = extract_fenced_blocks(text, language="json")
        assert len(blocks) == 1

    def test_extract_block_without_language(self):
        text = """
```
plain text
```
"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == ""
        assert blocks[0].content == "plain text"

    def test_extract_multiline_content(self):
        text = """
```json
{
    "key": "value",
    "nested": {
        "a": 1
    }
}
```
"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 1
        assert '"key": "value"' in blocks[0].content
        assert '"nested"' in blocks[0].content

    def test_no_blocks_returns_empty_list(self):
        text = "Just plain text without any code blocks"
        blocks = extract_fenced_blocks(text)
        assert blocks == []

    def test_fenced_block_has_line_numbers(self):
        text = """line 0
line 1
```json
content
```
line 5
"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].start_line == 2


class TestParseFencedBlocks:
    """Tests for parse_fenced_blocks function."""

    def test_parse_json_blocks(self):
        text = """
```json
{"first": 1}
```
```json
{"second": 2}
```
"""
        results = parse_fenced_blocks(text, "json", parse_json)
        assert results == [{"first": 1}, {"second": 2}]

    def test_parse_empty_when_no_blocks(self):
        text = "No blocks here"
        results = parse_fenced_blocks(text, "json", parse_json)
        assert results == []

    def test_parse_raises_on_invalid_content(self):
        text = """
```json
{invalid json}
```
"""
        with pytest.raises(Exception):  # JSONParseError
            parse_fenced_blocks(text, "json", parse_json)


class TestRenderedPromptBlockMethods:
    """Tests for RenderedPrompt fenced block methods."""

    def test_as_json_blocks(self):
        template = """
Here's some data:
```json
{"name": "Alice"}
```
And more:
```json
{"name": "Bob"}
```
"""
        spec = TemplateSpec.from_string(template)
        rendered = spec.render({})

        blocks = rendered.as_json_blocks()
        assert len(blocks) == 2
        assert blocks[0] == {"name": "Alice"}
        assert blocks[1] == {"name": "Bob"}

    def test_as_yaml_blocks(self):
        template = """
Config 1:
```yaml
name: Alice
age: 30
```
Config 2:
```yaml
name: Bob
age: 25
```
"""
        spec = TemplateSpec.from_string(template)
        rendered = spec.render({})

        blocks = rendered.as_yaml_blocks()
        assert len(blocks) == 2
        assert blocks[0] == {"name": "Alice", "age": 30}
        assert blocks[1] == {"name": "Bob", "age": 25}

    def test_as_xml_blocks(self):
        template = """
First:
```xml
<user id="1">Alice</user>
```
Second:
```xml
<user id="2">Bob</user>
```
"""
        spec = TemplateSpec.from_string(template)
        rendered = spec.render({})

        blocks = rendered.as_xml_blocks()
        assert len(blocks) == 2
        assert blocks[0].tag == "user"
        assert blocks[0].text == "Alice"
        assert blocks[1].tag == "user"
        assert blocks[1].text == "Bob"

    def test_as_xml_blocks_with_fragments(self):
        template = """
```xml
<a>first</a>
<b>second</b>
```
"""
        spec = TemplateSpec.from_string(template)
        rendered = spec.render({})

        blocks = rendered.as_xml_blocks()
        assert len(blocks) == 1
        # First block contains a list of elements (fragment)
        assert isinstance(blocks[0], list)
        assert len(blocks[0]) == 2

    def test_mixed_blocks_only_returns_requested_type(self):
        template = """
```json
{"type": "json"}
```
```yaml
type: yaml
```
```xml
<type>xml</type>
```
"""
        spec = TemplateSpec.from_string(template)
        rendered = spec.render({})

        json_blocks = rendered.as_json_blocks()
        assert len(json_blocks) == 1
        assert json_blocks[0]["type"] == "json"

        yaml_blocks = rendered.as_yaml_blocks()
        assert len(yaml_blocks) == 1
        assert yaml_blocks[0]["type"] == "yaml"

        xml_blocks = rendered.as_xml_blocks()
        assert len(xml_blocks) == 1
        assert xml_blocks[0].tag == "type"

    def test_no_blocks_returns_empty_list(self):
        spec = TemplateSpec.from_string("No code blocks here")
        rendered = spec.render({})

        assert rendered.as_json_blocks() == []
        assert rendered.as_yaml_blocks() == []
        assert rendered.as_xml_blocks() == []


class TestRenderedPromptAsXml:
    """Tests for RenderedPrompt.as_xml method."""

    def test_as_xml_single_root(self):
        spec = TemplateSpec.from_string("<root><child>value</child></root>")
        rendered = spec.render({})

        xml = rendered.as_xml()
        assert xml.tag == "root"
        assert xml.children[0].tag == "child"
        assert xml.children[0].text == "value"

    def test_as_xml_fragment(self):
        spec = TemplateSpec.from_string("<a>one</a><b>two</b>")
        rendered = spec.render({})

        xml = rendered.as_xml()
        assert isinstance(xml, list)
        assert len(xml) == 2
        assert xml[0].tag == "a"
        assert xml[1].tag == "b"

    def test_as_xml_strict_mode(self):
        spec = TemplateSpec.from_string("<a>one</a><b>two</b>")
        rendered = spec.render({})

        from jinjatest.parsers.xml_parser import XMLParseError

        with pytest.raises(XMLParseError):
            rendered.as_xml(strict=True)


class TestFencedBlockDataclass:
    """Tests for FencedBlock dataclass."""

    def test_fenced_block_attributes(self):
        block = FencedBlock(
            language="python",
            content="print('hello')",
            start_line=5,
            end_line=7,
        )
        assert block.language == "python"
        assert block.content == "print('hello')"
        assert block.start_line == 5
        assert block.end_line == 7
