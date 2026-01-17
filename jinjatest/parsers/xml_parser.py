"""Flexible XML parser for rendered template output.

Supports both valid XML documents and XML-like fragments commonly used
in prompts (e.g., multiple root elements, no XML declaration).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any


class XMLParseError(Exception):
    """Raised when XML parsing fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


@dataclass
class XMLElement:
    """Represents a parsed XML element.

    Attributes:
        tag: The element tag name.
        text: The text content of the element (stripped).
        tail: Text after the element's closing tag.
        attrib: Dictionary of element attributes.
        children: List of child XMLElement objects.
    """

    tag: str
    text: str | None = None
    tail: str | None = None
    attrib: dict[str, str] = field(default_factory=dict)
    children: list[XMLElement] = field(default_factory=list)

    @classmethod
    def from_etree(cls, element: ET.Element) -> XMLElement:
        """Create XMLElement from an ElementTree Element."""
        return cls(
            tag=element.tag,
            text=element.text.strip() if element.text else None,
            tail=element.tail.strip() if element.tail else None,
            attrib=dict(element.attrib),
            children=[cls.from_etree(child) for child in element],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary representation.

        Returns a dict with:
        - '@attr' for each attribute
        - '#text' for text content
        - tag names for children (as list if multiple with same tag)
        """
        result: dict[str, Any] = {}

        # Add attributes with @ prefix
        for key, value in self.attrib.items():
            result[f"@{key}"] = value

        # Add text content
        if self.text:
            result["#text"] = self.text

        # Add children
        for child in self.children:
            child_dict = child.to_dict()
            if child.tag in result:
                # Convert to list if multiple children with same tag
                existing = result[child.tag]
                if isinstance(existing, list):
                    existing.append(child_dict)
                else:
                    result[child.tag] = [existing, child_dict]
            else:
                result[child.tag] = child_dict

        return result

    def find(self, tag: str) -> XMLElement | None:
        """Find first child with given tag."""
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def find_all(self, tag: str) -> list[XMLElement]:
        """Find all children with given tag."""
        return [child for child in self.children if child.tag == tag]

    def get_text(self) -> str:
        """Get all text content including from children."""
        parts = []
        if self.text:
            parts.append(self.text)
        for child in self.children:
            parts.append(child.get_text())
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)


def _wrap_fragment(text: str) -> str:
    """Wrap XML fragment in a root element for parsing."""
    # Always wrap - we'll unwrap single elements later
    return f"<__root__>{text.strip()}</__root__>"


def parse_xml(text: str, *, strict: bool = False) -> XMLElement | list[XMLElement]:
    """Parse text as XML.

    Supports both valid XML documents and XML-like fragments.
    For fragments with multiple root elements, returns a list of XMLElement objects.

    Args:
        text: The text to parse as XML.
        strict: If True, requires valid XML with single root. If False (default),
               allows XML-like fragments with multiple root elements.

    Returns:
        XMLElement for single root documents, or list[XMLElement] for fragments.

    Raises:
        XMLParseError: If parsing fails.
    """
    stripped = text.strip()

    if not stripped:
        raise XMLParseError("Empty XML content")

    # Remove XML declaration if present
    stripped = re.sub(r"<\?xml[^?]*\?>", "", stripped).strip()

    if strict:
        try:
            root = ET.fromstring(stripped)
            return XMLElement.from_etree(root)
        except ET.ParseError as e:
            raise XMLParseError(f"Failed to parse XML: {e}", original_error=e) from e

    # Try parsing directly first
    try:
        root = ET.fromstring(stripped)
        return XMLElement.from_etree(root)
    except ET.ParseError:
        pass

    # Try wrapping in a root element for fragments
    try:
        wrapped = _wrap_fragment(stripped)
        root = ET.fromstring(wrapped)

        # If we used __root__, return children
        if root.tag == "__root__":
            children = [XMLElement.from_etree(child) for child in root]
            if len(children) == 1:
                return children[0]
            return children

        return XMLElement.from_etree(root)
    except ET.ParseError as e:
        raise XMLParseError(
            f"Failed to parse XML-like content: {e}", original_error=e
        ) from e
