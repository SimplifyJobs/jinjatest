"""Tests for parser modules."""

import pytest

from jinjatest.parsers.json_parser import JSONParseError, parse_json
from jinjatest.parsers.yaml_parser import YAMLParseError, parse_yaml


class TestJsonParser:
    """Tests for JSON parser."""

    def test_parse_valid_json_object(self):
        result = parse_json('{"name": "Alice", "age": 30}')
        assert result == {"name": "Alice", "age": 30}

    def test_parse_valid_json_array(self):
        result = parse_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_parse_json_string(self):
        result = parse_json('"hello"')
        assert result == "hello"

    def test_parse_json_number(self):
        result = parse_json("42")
        assert result == 42

    def test_parse_json_float(self):
        result = parse_json("3.14")
        assert result == 3.14

    def test_parse_json_boolean(self):
        assert parse_json("true") is True
        assert parse_json("false") is False

    def test_parse_json_null(self):
        assert parse_json("null") is None

    def test_parse_json_with_leading_whitespace(self):
        result = parse_json('   {"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_trailing_whitespace(self):
        result = parse_json('{"key": "value"}   ')
        assert result == {"key": "value"}

    def test_parse_json_with_newlines(self):
        result = parse_json('\n\n{"key": "value"}\n\n')
        assert result == {"key": "value"}

    def test_parse_invalid_json_raises_error(self):
        with pytest.raises(JSONParseError) as exc_info:
            parse_json("{invalid}")
        assert "Failed to parse JSON" in str(exc_info.value)

    def test_json_error_message_includes_location(self):
        with pytest.raises(JSONParseError) as exc_info:
            parse_json('{"key": }')
        error_msg = str(exc_info.value)
        assert "line" in error_msg
        assert "column" in error_msg

    def test_json_error_preserves_original(self):
        with pytest.raises(JSONParseError) as exc_info:
            parse_json("{bad json}")
        assert exc_info.value.original_error is not None

    def test_parse_nested_json(self):
        result = parse_json('{"outer": {"inner": [1, 2, 3]}}')
        assert result == {"outer": {"inner": [1, 2, 3]}}


class TestYamlParser:
    """Tests for YAML parser."""

    def test_parse_valid_yaml_dict(self):
        result = parse_yaml("name: Alice\nage: 30")
        assert result == {"name": "Alice", "age": 30}

    def test_parse_valid_yaml_list(self):
        result = parse_yaml("- one\n- two\n- three")
        assert result == ["one", "two", "three"]

    def test_parse_yaml_string(self):
        result = parse_yaml("hello")
        assert result == "hello"

    def test_parse_yaml_number(self):
        result = parse_yaml("42")
        assert result == 42

    def test_parse_yaml_float(self):
        result = parse_yaml("3.14")
        assert result == 3.14

    def test_parse_yaml_boolean(self):
        assert parse_yaml("true") is True
        assert parse_yaml("false") is False

    def test_parse_yaml_null(self):
        assert parse_yaml("null") is None
        assert parse_yaml("~") is None

    def test_parse_yaml_empty_string(self):
        assert parse_yaml("") is None

    def test_parse_invalid_yaml_raises_error(self):
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml("foo: bar: baz: invalid")
        assert "Failed to parse YAML" in str(exc_info.value)

    def test_yaml_error_preserves_original(self):
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml(":\n  - invalid")
        assert exc_info.value.original_error is not None

    def test_parse_nested_yaml(self):
        yaml_text = """
outer:
  inner:
    - one
    - two
"""
        result = parse_yaml(yaml_text)
        assert result == {"outer": {"inner": ["one", "two"]}}

    def test_parse_yaml_multiline_string(self):
        yaml_text = """
description: |
  This is a
  multiline string
"""
        result = parse_yaml(yaml_text)
        assert "This is a\nmultiline string\n" == result["description"]


class TestYamlParserAdditional:
    """Additional YAML parser tests."""

    def test_parse_yaml_complex_structure(self):
        yaml_text = """
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
"""
        result = parse_yaml(yaml_text)
        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == 5432

    def test_yaml_parse_error_attributes(self):
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml("invalid: yaml: content: [")
        assert exc_info.value.original_error is not None


class TestJsonParserAdditional:
    """Additional JSON parser tests."""

    def test_json_parse_error_without_original(self):
        err = JSONParseError("Test message")
        assert str(err) == "Test message"
        assert err.original_error is None

    def test_json_parse_error_with_original(self):
        original = ValueError("original error")
        err = JSONParseError("Test message", original_error=original)
        assert err.original_error is original
