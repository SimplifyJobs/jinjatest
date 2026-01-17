"""Fenced code block extraction for rendered template output.

Extracts and parses content from markdown-style fenced code blocks
(```language ... ```) in rendered templates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class FencedBlock:
    """A fenced code block extracted from text.

    Attributes:
        language: The language tag (e.g., 'json', 'yaml', 'xml').
        content: The raw content inside the block.
        start_line: Line number where block starts.
        end_line: Line number where block ends.
    """

    language: str
    content: str
    start_line: int
    end_line: int


# Pattern to match fenced code blocks: ```language\n...\n```
FENCED_BLOCK_PATTERN = re.compile(
    r"^```(\w*)\s*\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


def extract_fenced_blocks(text: str, language: str | None = None) -> list[FencedBlock]:
    """Extract fenced code blocks from text.

    Args:
        text: The text to search for fenced blocks.
        language: Optional language filter. If provided, only blocks with
                 this language tag are returned. Case-insensitive.

    Returns:
        List of FencedBlock objects found in the text.
    """
    blocks: list[FencedBlock] = []

    for match in FENCED_BLOCK_PATTERN.finditer(text):
        block_lang = match.group(1).lower() if match.group(1) else ""
        content = match.group(2)

        # Calculate line numbers
        start_pos = match.start()
        start_line = text[:start_pos].count("\n")
        end_line = start_line + content.count("\n") + 2  # +2 for ``` lines

        # Filter by language if specified
        if language is not None:
            if block_lang != language.lower():
                continue

        blocks.append(
            FencedBlock(
                language=block_lang,
                content=content.strip(),
                start_line=start_line,
                end_line=end_line,
            )
        )

    return blocks


def parse_fenced_blocks(
    text: str,
    language: str,
    parser: Callable[[str], Any],
) -> list[Any]:
    """Extract and parse fenced code blocks.

    Args:
        text: The text to search for fenced blocks.
        language: The language tag to filter for.
        parser: A function to parse the content of each block.

    Returns:
        List of parsed objects from matching blocks.

    Raises:
        The parser function may raise exceptions for invalid content.
    """
    blocks = extract_fenced_blocks(text, language=language)
    return [parser(block.content) for block in blocks]
