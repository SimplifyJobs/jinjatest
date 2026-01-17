"""JSON parser for rendered template output."""

from __future__ import annotations

import json
from typing import Any


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def parse_json(text: str) -> Any:
    """Parse text as JSON.

    Args:
        text: The text to parse as JSON.

    Returns:
        The parsed JSON value (dict, list, str, int, float, bool, or None).

    Raises:
        JSONParseError: If parsing fails.
    """
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise JSONParseError(
            f"Failed to parse JSON: {e.msg} at line {e.lineno}, column {e.colno}",
            original_error=e,
        ) from e
