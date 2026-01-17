"""Markdown section parser for structured template output."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MarkdownSection:
    """A markdown section with heading and content."""

    level: int
    title: str
    content: str
    start_line: int
    end_line: int

    @property
    def full_text(self) -> str:
        """Get the full text including the heading."""
        heading = "#" * self.level + " " + self.title
        if self.content:
            return heading + "\n" + self.content
        return heading


# Pattern to match markdown headings (# to ######)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", re.MULTILINE)


def parse_markdown_sections(text: str) -> list[MarkdownSection]:
    """Parse text into markdown sections based on headings.

    Args:
        text: Markdown text to parse.

    Returns:
        List of MarkdownSection objects, one per heading found.
        Content between headings is assigned to the preceding heading.
    """
    lines = text.split("\n")
    sections: list[MarkdownSection] = []

    # Find all headings with their line numbers
    headings: list[tuple[int, int, str]] = []  # (line_num, level, title)

    for i, line in enumerate(lines):
        match = HEADING_PATTERN.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append((i, level, title))

    # Build sections from headings
    for idx, (line_num, level, title) in enumerate(headings):
        # Content starts on the line after the heading
        content_start = line_num + 1

        # Content ends at the next heading or end of document
        if idx + 1 < len(headings):
            content_end = headings[idx + 1][0]
        else:
            content_end = len(lines)

        # Extract content lines and strip trailing empty lines
        content_lines = lines[content_start:content_end]
        while content_lines and not content_lines[-1].strip():
            content_lines.pop()
        while content_lines and not content_lines[0].strip():
            content_lines.pop(0)

        content = "\n".join(content_lines)

        sections.append(
            MarkdownSection(
                level=level,
                title=title,
                content=content,
                start_line=line_num,
                end_line=content_end,
            )
        )

    return sections


def find_section_by_title(
    sections: list[MarkdownSection], title: str
) -> MarkdownSection | None:
    """Find a section by its title (case-insensitive).

    Args:
        sections: List of MarkdownSection objects.
        title: The title to search for.

    Returns:
        The first matching section, or None if not found.
    """
    title_lower = title.lower()
    for section in sections:
        if section.title.lower() == title_lower:
            return section
    return None
