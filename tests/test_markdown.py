"""Tests for markdown parsing functionality."""

from pathlib import Path

from pydantic import BaseModel

from jinjatest import TemplateSpec, parse_markdown_sections


class MarkdownContext(BaseModel):
    title: str
    description: str
    features: list[str]
    plan: str


TEMPLATE_DIR = Path(__file__).parent / "templates"


class TestMarkdownParsing:
    """Test markdown section parsing."""

    def test_parse_sections(self) -> None:
        """Test parsing markdown sections."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "markdown.j2",
            context_model=MarkdownContext,
        )
        rendered = spec.render(
            {
                "title": "My Product",
                "description": "A great product.",
                "features": ["Fast", "Reliable", "Secure"],
                "plan": "pro",
            }
        )

        sections = rendered.as_markdown_sections()

        assert len(sections) == 3

        # Check main title
        assert sections[0].level == 1
        assert sections[0].title == "My Product"
        assert "A great product" in sections[0].content

        # Check Features section
        assert sections[1].level == 2
        assert sections[1].title == "Features"
        assert "Fast" in sections[1].content
        assert "Reliable" in sections[1].content

        # Check Pricing section
        assert sections[2].level == 2
        assert sections[2].title == "Pricing"
        assert "$99/month" in sections[2].content

    def test_find_section_by_title(self) -> None:
        """Test finding sections by title."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "markdown.j2",
            context_model=MarkdownContext,
        )
        rendered = spec.render(
            {
                "title": "Product",
                "description": "Description",
                "features": ["Feature1"],
                "plan": "free",
            }
        )

        pricing = rendered.markdown_section("Pricing")
        assert pricing is not None
        assert "Free tier" in pricing.content

        features = rendered.markdown_section("Features")
        assert features is not None
        assert "Feature1" in features.content

    def test_section_not_found(self) -> None:
        """Test that missing section returns None."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "markdown.j2",
            context_model=MarkdownContext,
        )
        rendered = spec.render(
            {
                "title": "Product",
                "description": "Description",
                "features": [],
                "plan": "free",
            }
        )

        assert rendered.markdown_section("Nonexistent") is None

    def test_case_insensitive_search(self) -> None:
        """Test that section search is case-insensitive."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "markdown.j2",
            context_model=MarkdownContext,
        )
        rendered = spec.render(
            {
                "title": "Product",
                "description": "Description",
                "features": [],
                "plan": "free",
            }
        )

        # Should find regardless of case
        assert rendered.markdown_section("FEATURES") is not None
        assert rendered.markdown_section("features") is not None
        assert rendered.markdown_section("Features") is not None


class TestMarkdownParserDirect:
    """Test the markdown parser directly."""

    def test_parse_nested_headings(self) -> None:
        """Test parsing nested heading levels."""
        text = """# Title

## Section 1

Content 1

### Subsection 1.1

Sub content

## Section 2

Content 2
"""
        sections = parse_markdown_sections(text)

        assert len(sections) == 4
        assert sections[0].level == 1
        assert sections[1].level == 2
        assert sections[2].level == 3
        assert sections[3].level == 2

    def test_section_full_text(self) -> None:
        """Test getting full text including heading."""
        text = """# Title

Some content here.
"""
        sections = parse_markdown_sections(text)

        assert sections[0].full_text.startswith("# Title")
        assert "Some content here" in sections[0].full_text

    def test_empty_content_section(self) -> None:
        """Test section with no content."""
        text = """# Title
## Empty Section
## Next Section

With content.
"""
        sections = parse_markdown_sections(text)

        empty_section = next(s for s in sections if s.title == "Empty Section")
        assert empty_section.content == ""

        next_section = next(s for s in sections if s.title == "Next Section")
        assert "With content" in next_section.content
