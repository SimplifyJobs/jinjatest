"""JSON parser for rendered template output."""

from __future__ import annotations

import json
import re
from typing import Any


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


# Regex patterns for stripping comments
# Single-line comment: // ... to end of line
_SINGLE_LINE_COMMENT = re.compile(r"//[^\n]*")
# Multi-line comment: /* ... */
_MULTI_LINE_COMMENT = re.compile(r"/\*[\s\S]*?\*/")


def _strip_json_comments(text: str) -> str:
    """Strip C-style comments from JSON text.

    Handles:
    - Single-line comments: // comment
    - Multi-line comments: /* comment */

    Note: This is a simple implementation that doesn't handle comments
    inside strings perfectly, but works for most practical cases.
    """
    # Remove multi-line comments first (they can span lines)
    text = _MULTI_LINE_COMMENT.sub("", text)
    # Then remove single-line comments
    text = _SINGLE_LINE_COMMENT.sub("", text)
    return text


def parse_json(text: str, *, allow_comments: bool = False) -> Any:
    """Parse text as JSON.

    Args:
        text: The text to parse as JSON.
        allow_comments: If True, strip C-style comments (// and /* */)
            before parsing. Useful for JSONC-style configuration files.
            Default is False for strict JSON compliance.

    Returns:
        The parsed JSON value (dict, list, str, int, float, bool, or None).

    Raises:
        JSONParseError: If parsing fails.

    Example:
        >>> parse_json('{"key": "value"}')
        {'key': 'value'}

        >>> parse_json('''
        ... {
        ...     // This is a comment
        ...     "key": "value"
        ... }
        ... ''', allow_comments=True)
        {'key': 'value'}
    """
    text = text.strip()

    if allow_comments:
        text = _strip_json_comments(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise JSONParseError(
            f"Failed to parse JSON: {e.msg} at line {e.lineno}, column {e.colno}",
            original_error=e,
        ) from e
