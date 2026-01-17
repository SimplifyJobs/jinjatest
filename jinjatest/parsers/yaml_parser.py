"""YAML parser for rendered template output.

Requires pyyaml to be installed (pip install jinjatest[yaml]).
"""

from __future__ import annotations

from typing import Any

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "YAML parsing requires pyyaml. Install with: pip install jinjatest[yaml]"
    ) from e


class YAMLParseError(Exception):
    """Raised when YAML parsing fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def parse_yaml(text: str) -> Any:
    """Parse text as YAML.

    Args:
        text: The text to parse as YAML.

    Returns:
        The parsed YAML value.

    Raises:
        YAMLParseError: If parsing fails.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise YAMLParseError(f"Failed to parse YAML: {e}", original_error=e) from e
