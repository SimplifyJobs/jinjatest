"""
Parsers for interpreting rendered template output.

Provides adapters to parse rendered text as:
- JSON
- YAML (optional, requires pyyaml)
- XML (flexible, supports XML-like fragments)
- Markdown sections
- Fenced code blocks
"""

from __future__ import annotations

from jinjatest.parsers.fenced_blocks import (
    FencedBlock,
    extract_fenced_blocks,
    parse_fenced_blocks,
)
from jinjatest.parsers.json_parser import JSONParseError, parse_json
from jinjatest.parsers.markdown import MarkdownSection, parse_markdown_sections
from jinjatest.parsers.xml_parser import XMLElement, XMLParseError, parse_xml

__all__ = [
    "parse_json",
    "JSONParseError",
    "parse_xml",
    "XMLParseError",
    "XMLElement",
    "parse_markdown_sections",
    "MarkdownSection",
    "extract_fenced_blocks",
    "parse_fenced_blocks",
    "FencedBlock",
]

# Optional YAML support
try:
    from jinjatest.parsers.yaml_parser import YAMLParseError, parse_yaml  # noqa: F401

    __all__.extend(["parse_yaml", "YAMLParseError"])
except ImportError:
    pass
