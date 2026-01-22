"""JSON parser for rendered template output."""

from __future__ import annotations

import json
from typing import Any


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def _is_escaped(text: str, pos: int) -> bool:
    """Check if character at pos is escaped by counting preceding backslashes."""
    num_backslashes = 0
    pos -= 1
    while pos >= 0 and text[pos] == "\\":
        num_backslashes += 1
        pos -= 1
    # Odd number of backslashes means the character is escaped
    return num_backslashes % 2 == 1


def _strip_json_comments(text: str) -> str:
    """Strip C-style comments from JSON text.

    Handles:
    - Single-line comments: // comment
    - Multi-line comments: /* comment */

    Properly handles comments inside strings (leaves them untouched),
    including escaped quotes and escaped backslashes.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        char = text[i]

        # Handle string state - check for unescaped quotes
        if char == '"' and not _is_escaped(text, i):
            in_string = not in_string
            result.append(char)
            i += 1
        elif in_string:
            # Inside a string - copy everything including escape sequences
            result.append(char)
            i += 1
        elif char == "/" and i + 1 < n:
            next_char = text[i + 1]
            if next_char == "/":
                # Single-line comment - skip to end of line
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
            elif next_char == "*":
                # Multi-line comment - skip to */
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2  # Skip the closing */
            else:
                result.append(char)
                i += 1
        else:
            result.append(char)
            i += 1

    return "".join(result)


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
