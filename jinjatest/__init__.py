"""
jinjatest - A type-safe, structured testing library for Jinja templates.

This library provides tools for testing Jinja templates with:
- Type-safe context validation using Pydantic
- Structured output parsing (JSON, YAML, XML, Markdown, fenced code blocks)
- Test instrumentation with anchors and traces
- Pytest integration with fixtures and snapshots

Example:
    from pydantic import BaseModel
    from jinjatest import TemplateSpec, PromptAsserts

    class Ctx(BaseModel):
        user_name: str
        plan: str

    spec = TemplateSpec.from_file("prompts/welcome.j2", context_model=Ctx)

    def test_welcome_pro_user():
        rendered = spec.render({"user_name": "Ada", "plan": "pro"})
        a = PromptAsserts(rendered).normalized()
        a.contains("Hello, Ada")
        a.not_contains("Upgrade now")
"""

from __future__ import annotations

from jinjatest.asserts import PromptAssertionError, PromptAsserts, assert_no_undefined
from jinjatest.instrumentation import (
    ProductionInstrumentation,
    TestInstrumentation,
)
from jinjatest.markers import (
    TemplateMarkers,
    discover_markers,
    has_markers,
)
from jinjatest.parsers import (
    FencedBlock,
    JSONParseError,
    MarkdownSection,
    XMLElement,
    XMLParseError,
    extract_fenced_blocks,
    parse_fenced_blocks,
    parse_json,
    parse_markdown_sections,
    parse_xml,
)
from jinjatest.rendered import RenderedPrompt, RenderedPromptSection, normalize_text
from jinjatest.spec import (
    ContextValidationError,
    TemplateRenderError,
    TemplateSpec,
    UndeclaredVariableError,
    create_environment,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Core classes
    "TemplateSpec",
    "RenderedPrompt",
    "RenderedPromptSection",
    # Assertions
    "PromptAsserts",
    "PromptAssertionError",
    "assert_no_undefined",
    # Environment
    "create_environment",
    # Exceptions
    "TemplateRenderError",
    "ContextValidationError",
    "UndeclaredVariableError",
    "JSONParseError",
    "XMLParseError",
    # Parsers
    "parse_json",
    "parse_xml",
    "parse_markdown_sections",
    "MarkdownSection",
    "XMLElement",
    # Fenced blocks
    "extract_fenced_blocks",
    "parse_fenced_blocks",
    "FencedBlock",
    # Instrumentation (for type hints)
    "TestInstrumentation",
    "ProductionInstrumentation",
    # Markers (comment-based)
    "has_markers",
    "discover_markers",
    "TemplateMarkers",
    # Utilities
    "normalize_text",
    # Coverage (lazy import via jinjatest.coverage)
]

# Optional YAML exports
try:
    from jinjatest.parsers import YAMLParseError, parse_yaml  # noqa: F401

    __all__.extend(["parse_yaml", "YAMLParseError"])
except ImportError:
    pass
