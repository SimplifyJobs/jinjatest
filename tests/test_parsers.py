"""Tests for parser modules."""

import pytest

from jinjatest.parsers.json_parser import (
    JSONParseError,
    _strip_json_comments,
    parse_json,
)
from jinjatest.parsers.yaml_parser import YAMLParseError, parse_yaml


class TestStripJsonComments:
    """Tests for _strip_json_comments function with edge cases."""

    def test_no_comments(self):
        """Plain JSON without comments passes through unchanged."""
        text = '{"key": "value"}'
        assert _strip_json_comments(text) == text

    def test_single_line_comment_at_end(self):
        """Single-line comment at end of line is removed."""
        text = '{"key": "value"} // comment'
        assert _strip_json_comments(text) == '{"key": "value"} '

    def test_single_line_comment_own_line(self):
        """Single-line comment on its own line is removed."""
        text = '{\n// comment\n"key": "value"\n}'
        assert _strip_json_comments(text) == '{\n\n"key": "value"\n}'

    def test_multi_line_comment(self):
        """Multi-line comment is removed."""
        text = '{"key": /* comment */ "value"}'
        assert _strip_json_comments(text) == '{"key":  "value"}'

    def test_multi_line_comment_spanning_lines(self):
        """Multi-line comment spanning multiple lines is removed."""
        text = '{\n/* line1\nline2\nline3 */\n"key": "value"}'
        assert _strip_json_comments(text) == '{\n\n"key": "value"}'

    def test_url_in_string_preserved(self):
        """URLs inside strings are not corrupted."""
        text = '{"url": "https://example.com/path"}'
        assert _strip_json_comments(text) == text

    def test_double_slash_in_string_preserved(self):
        """Double slashes inside strings are preserved."""
        text = '{"note": "use // for comments"}'
        assert _strip_json_comments(text) == text

    def test_block_comment_pattern_in_string_preserved(self):
        """Block comment patterns inside strings are preserved."""
        text = '{"note": "use /* */ for blocks"}'
        assert _strip_json_comments(text) == text

    def test_escaped_quote_in_string(self):
        """Escaped quotes inside strings don't break parsing."""
        text = r'{"say": "hello \"world\"", "x": 1} // comment'
        result = _strip_json_comments(text)
        assert result == r'{"say": "hello \"world\"", "x": 1} '

    def test_escaped_quote_followed_by_comment_pattern(self):
        """Escaped quote followed by // doesn't start a comment."""
        text = r'{"msg": "say \"hi\" // ok"}'
        assert _strip_json_comments(text) == text

    def test_backslash_in_string(self):
        """Backslashes in strings are handled correctly."""
        text = r'{"path": "C:\\Users\\name"}'
        assert _strip_json_comments(text) == text

    def test_empty_string_with_comment_after(self):
        """Empty string followed by comment."""
        text = '{"empty": ""} // comment'
        assert _strip_json_comments(text) == '{"empty": ""} '

    def test_multiple_strings_same_line(self):
        """Multiple strings on same line with comment."""
        text = '{"a": "x", "b": "y"} // comment'
        assert _strip_json_comments(text) == '{"a": "x", "b": "y"} '

    def test_string_with_newline_escape(self):
        """String containing escaped newline."""
        text = r'{"text": "line1\nline2"} // comment'
        assert _strip_json_comments(text) == r'{"text": "line1\nline2"} '

    def test_consecutive_single_line_comments(self):
        """Multiple single-line comments in a row."""
        text = '{\n// comment 1\n// comment 2\n"key": "value"}'
        assert _strip_json_comments(text) == '{\n\n\n"key": "value"}'

    def test_consecutive_slashes_outside_string(self):
        """//// is treated as comment starting with //."""
        text = '{"key": "value"} //// comment'
        assert _strip_json_comments(text) == '{"key": "value"} '

    def test_empty_block_comment(self):
        """Empty block comment /**/ is removed."""
        text = '{"key": /**/ "value"}'
        assert _strip_json_comments(text) == '{"key":  "value"}'

    def test_nested_comment_pattern_in_block(self):
        """// inside /* */ is part of the block comment."""
        text = '{"key": /* // nested */ "value"}'
        assert _strip_json_comments(text) == '{"key":  "value"}'

    def test_comment_at_very_start(self):
        """Comment at the very start of input."""
        text = '// comment\n{"key": "value"}'
        assert _strip_json_comments(text) == '\n{"key": "value"}'

    def test_comment_at_very_end(self):
        """Comment at the very end with no newline."""
        text = '{"key": "value"} // comment'
        assert _strip_json_comments(text) == '{"key": "value"} '

    def test_only_comments(self):
        """Input that is only comments."""
        text = "// comment 1\n/* comment 2 */"
        assert _strip_json_comments(text) == "\n"

    def test_string_ending_with_backslash_before_real_quote(self):
        """String with backslash that is NOT escaping the closing quote."""
        # In JSON: "foo\\" means the string "foo\" (backslash at end)
        # The \\\\ in Python raw string = \\ in actual string = \ in JSON string value
        text = r'{"path": "foo\\"} // comment'
        result = _strip_json_comments(text)
        # The comment should be removed
        assert result == r'{"path": "foo\\"} '

    def test_complex_mixed_case(self):
        """Complex case with multiple strings, escapes, and comments."""
        text = """{
            // Config file
            "url": "https://example.com",  /* API endpoint */
            "pattern": "use // for docs",
            "escape": "say \\"hello\\"",
            "path": "C:\\\\Users"  // Windows path
        }"""
        result = _strip_json_comments(text)
        # Verify strings are intact
        assert '"url": "https://example.com"' in result
        assert '"pattern": "use // for docs"' in result
        assert r'"escape": "say \"hello\""' in result
        assert r'"path": "C:\\Users"' in result
        # Verify comments are removed
        assert "// Config file" not in result
        assert "/* API endpoint */" not in result
        assert "// Windows path" not in result


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

    def test_parse_json_with_single_line_comments(self):
        """Test parsing JSON with // comments when allow_comments=True."""
        json_text = """{
            // This is a comment
            "name": "Alice",
            "age": 30  // inline comment
        }"""
        result = parse_json(json_text, allow_comments=True)
        assert result == {"name": "Alice", "age": 30}

    def test_parse_json_with_multi_line_comments(self):
        """Test parsing JSON with /* */ comments when allow_comments=True."""
        json_text = """{
            /* This is a
               multi-line comment */
            "name": "Bob",
            "active": true
        }"""
        result = parse_json(json_text, allow_comments=True)
        assert result == {"name": "Bob", "active": True}

    def test_parse_json_with_mixed_comments(self):
        """Test parsing JSON with both comment styles when allow_comments=True."""
        json_text = """{
            // Single line comment
            "items": [
                /* block comment */ 1,
                2,  // trailing comment
                3
            ]
        }"""
        result = parse_json(json_text, allow_comments=True)
        assert result == {"items": [1, 2, 3]}

    def test_parse_json_comments_disabled_by_default(self):
        """Test that comments cause parse error when allow_comments=False (default)."""
        json_text = '{"key": "value"} // comment'
        with pytest.raises(JSONParseError):
            parse_json(json_text)

    def test_parse_json_allow_comments_false_explicit(self):
        """Test that allow_comments=False rejects comments."""
        json_text = '{"key": "value"} // comment'
        with pytest.raises(JSONParseError):
            parse_json(json_text, allow_comments=False)

    def test_parse_json_preserves_url_in_string(self):
        """Test that URLs inside strings are not corrupted by comment stripping."""
        json_text = '{"url": "https://example.com/path"}'
        result = parse_json(json_text, allow_comments=True)
        assert result == {"url": "https://example.com/path"}

    def test_parse_json_preserves_comment_like_patterns_in_strings(self):
        """Test that // and /* inside strings are preserved."""
        json_text = """{
            "note": "Use // for single-line comments",
            "other": "And /* */ for blocks"
        }"""
        result = parse_json(json_text, allow_comments=True)
        assert result["note"] == "Use // for single-line comments"
        assert result["other"] == "And /* */ for blocks"

    def test_parse_json_mixed_real_comments_and_string_patterns(self):
        """Test real comments are removed but string content preserved."""
        json_text = """{
            // This comment should be removed
            "url": "https://example.com",  /* also removed */
            "desc": "Visit // our site"
        }"""
        result = parse_json(json_text, allow_comments=True)
        assert result == {
            "url": "https://example.com",
            "desc": "Visit // our site",
        }


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
