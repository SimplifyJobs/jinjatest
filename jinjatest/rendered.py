"""
RenderedPrompt class and related utilities.

Holds rendered template output with query and assertion helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from jinjatest.instrumentation import AnchorIndex
from jinjatest.parsers.fenced_blocks import parse_fenced_blocks
from jinjatest.parsers.json_parser import parse_json
from jinjatest.parsers.markdown import (
    MarkdownSection,
    find_section_by_title,
    parse_markdown_sections,
)
from jinjatest.parsers.xml_parser import XMLElement, parse_xml

if TYPE_CHECKING:
    pass


def normalize_text(
    text: str, *, collapse_whitespace: bool = True, strip_lines: bool = True
) -> str:
    """Normalize text for comparison.

    Args:
        text: The text to normalize.
        collapse_whitespace: If True, collapse multiple spaces/tabs to single space.
        strip_lines: If True, strip trailing whitespace from each line.

    Returns:
        Normalized text.
    """
    lines = text.split("\n")

    if strip_lines:
        lines = [line.rstrip() for line in lines]

    result = "\n".join(lines)

    if collapse_whitespace:
        # Collapse multiple spaces/tabs to single space (but preserve newlines)
        result = re.sub(r"[ \t]+", " ", result)

    # Collapse multiple blank lines to single blank line
    result = re.sub(r"\n{3,}", "\n\n", result)

    # Strip leading/trailing whitespace
    result = result.strip()

    return result


@dataclass
class RenderedPromptSection:
    """A view into a section of a rendered prompt."""

    name: str
    text: str
    _parent: RenderedPrompt | None = field(default=None, repr=False)

    @property
    def normalized(self) -> str:
        """Get normalized text of this section."""
        return normalize_text(self.text)

    def contains(self, substring: str) -> bool:
        """Check if section contains substring."""
        return substring in self.text

    def not_contains(self, substring: str) -> bool:
        """Check if section does not contain substring."""
        return substring not in self.text

    def matches(self, pattern: str, flags: int = 0) -> bool:
        """Check if section matches regex pattern."""
        return bool(re.search(pattern, self.text, flags))


@dataclass
class RenderedPrompt:
    """Holds rendered template output with query helpers.

    Attributes:
        text: The raw rendered text.
        trace_events: List of trace events recorded during rendering (if instrumentation enabled).
        anchor_index: Index of anchor positions (if instrumentation enabled).
    """

    text: str
    trace_events: list[str] = field(default_factory=list)
    anchor_index: AnchorIndex | None = None

    @property
    def normalized(self) -> str:
        """Get normalized text (whitespace-collapsed, trimmed)."""
        base_text = self.anchor_index.clean_text if self.anchor_index else self.text
        return normalize_text(base_text)

    @property
    def clean_text(self) -> str:
        """Get text with anchor markers removed (if any)."""
        if self.anchor_index:
            return self.anchor_index.clean_text
        return self.text

    @property
    def lines(self) -> list[str]:
        """Get text as list of lines."""
        return self.clean_text.split("\n")

    @property
    def normalized_lines(self) -> list[str]:
        """Get normalized text as list of lines."""
        return self.normalized.split("\n")

    # Section access methods

    def section(self, name: str) -> RenderedPromptSection:
        """Get a named section (by anchor).

        Args:
            name: The anchor name.

        Returns:
            A RenderedPromptSection view.

        Raises:
            KeyError: If the anchor doesn't exist.
        """
        if self.anchor_index is None:
            raise KeyError(
                f"No anchors available. Enable instrumentation to use sections. Anchor '{name}' not found."
            )

        section_text = self.anchor_index.get_section(name)
        if section_text is None:
            available = ", ".join(self.anchor_index.list_anchors()) or "(none)"
            raise KeyError(f"Anchor '{name}' not found. Available anchors: {available}")

        return RenderedPromptSection(name=name, text=section_text, _parent=self)

    def sections(self) -> dict[str, RenderedPromptSection]:
        """Get all sections as a dictionary.

        Returns:
            Dictionary mapping anchor names to RenderedPromptSection views.
        """
        if self.anchor_index is None:
            return {}

        return {
            name: RenderedPromptSection(
                name=name, text=self.anchor_index.get_section(name) or "", _parent=self
            )
            for name in self.anchor_index.list_anchors()
        }

    def has_section(self, name: str) -> bool:
        """Check if a named section exists."""
        if self.anchor_index is None:
            return False
        return self.anchor_index.has_anchor(name)

    # Parsing methods

    def as_json(self) -> Any:
        """Parse the rendered text as JSON.

        Returns:
            The parsed JSON value.

        Raises:
            JSONParseError: If parsing fails.
        """
        return parse_json(self.clean_text)

    def as_yaml(self) -> Any:
        """Parse the rendered text as YAML.

        Requires pyyaml to be installed.

        Returns:
            The parsed YAML value.

        Raises:
            YAMLParseError: If parsing fails.
            ImportError: If pyyaml is not installed.
        """
        from jinjatest.parsers.yaml_parser import parse_yaml

        return parse_yaml(self.clean_text)

    def as_markdown_sections(self) -> list[MarkdownSection]:
        """Parse the rendered text as markdown sections.

        Returns:
            List of MarkdownSection objects.
        """
        return parse_markdown_sections(self.clean_text)

    def markdown_section(self, title: str) -> MarkdownSection | None:
        """Find a markdown section by title.

        Args:
            title: The section title to find (case-insensitive).

        Returns:
            The MarkdownSection if found, None otherwise.
        """
        return find_section_by_title(self.as_markdown_sections(), title)

    def as_xml(self, *, strict: bool = False) -> XMLElement | list[XMLElement]:
        """Parse the rendered text as XML.

        Supports both valid XML documents and XML-like fragments
        (multiple root elements, no XML declaration required).

        Args:
            strict: If True, requires valid XML with single root.
                   If False (default), allows XML-like fragments.

        Returns:
            XMLElement for single root, or list[XMLElement] for fragments.

        Raises:
            XMLParseError: If parsing fails.
        """
        return parse_xml(self.clean_text, strict=strict)

    # Fenced code block parsing methods

    def as_json_blocks(self) -> list[Any]:
        """Extract and parse all ```json fenced code blocks.

        Returns:
            List of parsed JSON objects, one per block found.

        Raises:
            JSONParseError: If any block contains invalid JSON.
        """
        return parse_fenced_blocks(self.clean_text, "json", parse_json)

    def as_yaml_blocks(self) -> list[Any]:
        """Extract and parse all ```yaml fenced code blocks.

        Requires pyyaml to be installed.

        Returns:
            List of parsed YAML objects, one per block found.

        Raises:
            YAMLParseError: If any block contains invalid YAML.
            ImportError: If pyyaml is not installed.
        """
        from jinjatest.parsers.yaml_parser import parse_yaml

        return parse_fenced_blocks(self.clean_text, "yaml", parse_yaml)

    def as_xml_blocks(
        self, *, strict: bool = False
    ) -> list[XMLElement | list[XMLElement]]:
        """Extract and parse all ```xml fenced code blocks.

        Args:
            strict: If True, requires valid XML with single root.
                   If False (default), allows XML-like fragments.

        Returns:
            List of parsed XMLElement objects, one per block found.

        Raises:
            XMLParseError: If any block contains invalid XML.
        """

        def parse_xml_with_strict(text: str) -> XMLElement | list[XMLElement]:
            return parse_xml(text, strict=strict)

        return parse_fenced_blocks(self.clean_text, "xml", parse_xml_with_strict)

    # Simple query helpers

    def contains(self, substring: str) -> bool:
        """Check if rendered text contains substring."""
        return substring in self.clean_text

    def not_contains(self, substring: str) -> bool:
        """Check if rendered text does not contain substring."""
        return substring not in self.clean_text

    def contains_line(self, line: str) -> bool:
        """Check if any line contains the given text."""
        return any(line in existing_line for existing_line in self.lines)

    def has_line(self, line: str) -> bool:
        """Check if the exact line exists."""
        return line in self.lines

    def matches(self, pattern: str, flags: int = 0) -> bool:
        """Check if text matches regex pattern."""
        return bool(re.search(pattern, self.clean_text, flags))

    def find_all(self, pattern: str, flags: int = 0) -> list[str]:
        """Find all matches of a regex pattern."""
        return re.findall(pattern, self.clean_text, flags)

    # Trace helpers

    def has_trace(self, event: str) -> bool:
        """Check if a trace event was recorded."""
        return event in self.trace_events

    def trace_count(self, event: str) -> int:
        """Count occurrences of a trace event."""
        return self.trace_events.count(event)
