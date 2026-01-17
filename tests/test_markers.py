"""Tests for comment-based markers functionality."""

import tempfile
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from jinjatest import (
    TemplateSpec,
    discover_markers,
    has_markers,
    instrument,
    load_template_with_markers,
    transform_markers,
)


class TestMarkerTransformation:
    """Tests for the transform_markers function."""

    def test_transform_anchor(self) -> None:
        """Test transforming a single anchor marker."""
        source = "{#jt:anchor:intro#}\nHello"
        result = transform_markers(source)
        assert '{{ jt.anchor("intro") }}' in result.source
        assert result.anchor_names == ["intro"]
        assert result.trace_names == []

    def test_transform_trace(self) -> None:
        """Test transforming a single trace marker."""
        source = "{% if x %}{#jt:trace:x_true#}{% endif %}"
        result = transform_markers(source)
        assert '{{ jt.trace("x_true") }}' in result.source
        assert result.trace_names == ["x_true"]
        assert result.anchor_names == []

    def test_transform_multiple(self) -> None:
        """Test transforming multiple markers."""
        source = "{#jt:anchor:a#}\n{#jt:anchor:b#}\n{#jt:trace:t#}"
        result = transform_markers(source)
        assert result.anchor_names == ["a", "b"]
        assert result.trace_names == ["t"]
        assert '{{ jt.anchor("a") }}' in result.source
        assert '{{ jt.anchor("b") }}' in result.source
        assert '{{ jt.trace("t") }}' in result.source

    def test_no_markers(self) -> None:
        """Test source without markers passes through unchanged."""
        source = "Hello {{ name }}"
        result = transform_markers(source)
        assert result.source == source
        assert result.anchor_names == []
        assert result.trace_names == []

    def test_invalid_marker_names_ignored(self) -> None:
        """Test that invalid identifiers are not transformed."""
        # These should NOT be transformed (invalid identifier - starts with number)
        source = "{#jt:anchor:123invalid#}"
        result = transform_markers(source)
        assert result.source == source  # Unchanged
        assert result.anchor_names == []

    def test_invalid_marker_with_hyphen_ignored(self) -> None:
        """Test that identifiers with hyphens are not transformed."""
        source = "{#jt:anchor:my-anchor#}"
        result = transform_markers(source)
        assert result.source == source  # Unchanged

    def test_valid_identifier_with_underscore(self) -> None:
        """Test that underscores in identifiers work."""
        source = "{#jt:anchor:my_anchor#}"
        result = transform_markers(source)
        assert '{{ jt.anchor("my_anchor") }}' in result.source
        assert result.anchor_names == ["my_anchor"]

    def test_valid_identifier_with_numbers(self) -> None:
        """Test that numbers after first character work."""
        source = "{#jt:anchor:section2#}"
        result = transform_markers(source)
        assert '{{ jt.anchor("section2") }}' in result.source

    def test_marker_inline_with_content(self) -> None:
        """Test markers can be inline with other content."""
        source = "Start {#jt:anchor:mid#} End"
        result = transform_markers(source)
        assert result.source == 'Start {{ jt.anchor("mid") }} End'

    def test_preserve_surrounding_jinja(self) -> None:
        """Test that surrounding Jinja syntax is preserved."""
        source = """{% if show %}
{#jt:anchor:content#}
{{ value }}
{% endif %}"""
        result = transform_markers(source)
        assert "{% if show %}" in result.source
        assert "{% endif %}" in result.source
        assert "{{ value }}" in result.source
        assert '{{ jt.anchor("content") }}' in result.source


class TestHasMarkers:
    """Tests for the has_markers function."""

    def test_has_anchor_marker(self) -> None:
        """Test detecting anchor markers."""
        assert has_markers("{#jt:anchor:x#}")

    def test_has_trace_marker(self) -> None:
        """Test detecting trace markers."""
        assert has_markers("{#jt:trace:y#}")

    def test_regular_comment_no_marker(self) -> None:
        """Test that regular Jinja comments are not detected."""
        assert not has_markers("regular {# comment #}")

    def test_function_call_no_marker(self) -> None:
        """Test that function call syntax is not detected as marker."""
        assert not has_markers("{{ jt.anchor('x') }}")

    def test_empty_string(self) -> None:
        """Test empty string has no markers."""
        assert not has_markers("")

    def test_mixed_content(self) -> None:
        """Test mixed content with marker."""
        assert has_markers("Hello {#jt:anchor:test#} World")


class TestDiscoverMarkers:
    """Tests for the discover_markers function."""

    def test_discover_all(self) -> None:
        """Test discovering all markers in a template."""
        source = """
        {#jt:anchor:system#}
        System content
        {#jt:anchor:user#}
        User content
        {% if x %}{#jt:trace:x_branch#}{% endif %}
        """
        markers = discover_markers(source)
        assert markers.anchors == ["system", "user"]
        assert markers.traces == ["x_branch"]
        assert markers.has_markers

    def test_discover_empty(self) -> None:
        """Test discovering markers in template without any."""
        markers = discover_markers("Hello {{ name }}")
        assert markers.anchors == []
        assert markers.traces == []
        assert not markers.has_markers

    def test_discover_only_anchors(self) -> None:
        """Test discovering only anchor markers."""
        markers = discover_markers("{#jt:anchor:a#}{#jt:anchor:b#}")
        assert markers.anchors == ["a", "b"]
        assert markers.traces == []
        assert markers.has_markers

    def test_discover_only_traces(self) -> None:
        """Test discovering only trace markers."""
        markers = discover_markers("{#jt:trace:t1#}{#jt:trace:t2#}")
        assert markers.anchors == []
        assert markers.traces == ["t1", "t2"]
        assert markers.has_markers


class TestTemplateSpecWithMarkers:
    """Tests for TemplateSpec integration with comment markers."""

    def test_from_string_transforms_markers(self) -> None:
        """Test that from_string transforms comment markers."""
        spec = TemplateSpec.from_string("{#jt:anchor:test#}\nHello {{ name }}")
        rendered = spec.render({"name": "World"})
        assert rendered.has_section("test")
        assert rendered.section("test").contains("Hello World")

    def test_anchor_sections_work(self) -> None:
        """Test that transformed anchor markers create working sections."""
        spec = TemplateSpec.from_string(
            """{#jt:anchor:system#}
You are a helpful assistant.

{#jt:anchor:user#}
User: {{ user_input }}"""
        )
        rendered = spec.render({"user_input": "Hello!"})

        assert rendered.has_section("system")
        assert rendered.has_section("user")
        assert "helpful assistant" in rendered.section("system").text
        assert "User: Hello!" in rendered.section("user").text

    def test_trace_in_conditional(self) -> None:
        """Test that transformed trace markers work in conditionals."""
        spec = TemplateSpec.from_string(
            """{% if show_extra %}
{#jt:trace:extra_shown#}
Extra content
{% endif %}"""
        )

        rendered = spec.render({"show_extra": True})
        assert rendered.has_trace("extra_shown")

        rendered = spec.render({"show_extra": False})
        assert not rendered.has_trace("extra_shown")

    def test_disable_marker_transformation(self) -> None:
        """Test disabling marker transformation."""
        spec = TemplateSpec.from_string(
            "{#jt:anchor:test#}\nHello",
            use_comment_markers=False,
        )
        rendered = spec.render({})
        # Marker was not transformed, so no section exists
        assert not rendered.has_section("test")
        # The comment is stripped by Jinja since it wasn't transformed
        assert "Hello" in rendered.text

    def test_markers_not_in_output(self) -> None:
        """Test that marker comments don't appear in production output."""
        # In test mode with markers, the markers are transformed to function calls
        # The anchor markers emit sentinel strings that are indexed but not visible
        spec = TemplateSpec.from_string("{#jt:anchor:test#}Hello World")
        rendered = spec.render({})
        # The clean_text should not contain the comment syntax
        assert "{#jt:" not in rendered.clean_text
        assert "Hello World" in rendered.clean_text

    def test_mixed_markers_and_function_calls(self) -> None:
        """Test mixing comment markers with function call syntax."""
        spec = TemplateSpec.from_string(
            """{#jt:anchor:comment_style#}
Comment-based section

{{ jt.anchor("function_style") }}
Function-based section"""
        )
        rendered = spec.render({})
        assert rendered.has_section("comment_style")
        assert rendered.has_section("function_style")

    def test_multiple_anchors_ordering(self) -> None:
        """Test that multiple anchors maintain correct ordering."""
        spec = TemplateSpec.from_string(
            """{#jt:anchor:first#}
First section
{#jt:anchor:second#}
Second section
{#jt:anchor:third#}
Third section"""
        )
        rendered = spec.render({})

        sections = rendered.sections()
        assert list(sections.keys()) == ["first", "second", "third"]

    def test_trace_count(self) -> None:
        """Test counting multiple trace events."""
        spec = TemplateSpec.from_string(
            """{% for i in items %}
{#jt:trace:item_processed#}
Item: {{ i }}
{% endfor %}"""
        )
        rendered = spec.render({"items": [1, 2, 3]})
        assert rendered.trace_count("item_processed") == 3


class TestTemplateSpecFromFile:
    """Tests for TemplateSpec.from_file with markers."""

    def test_from_file_transforms_markers(self) -> None:
        """Test that from_file transforms comment markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "test.j2"
            template_path.write_text(
                """{#jt:anchor:greeting#}
Hello, {{ name }}!"""
            )

            spec = TemplateSpec.from_file(template_path)
            rendered = spec.render({"name": "World"})

            assert rendered.has_section("greeting")
            assert "Hello, World!" in rendered.section("greeting").text

    def test_from_file_disable_markers(self) -> None:
        """Test disabling markers when loading from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "test.j2"
            template_path.write_text("{#jt:anchor:test#}Content")

            spec = TemplateSpec.from_file(template_path, use_comment_markers=False)
            rendered = spec.render({})

            assert not rendered.has_section("test")


class TestLoadTemplateWithMarkers:
    """Tests for the load_template_with_markers utility function."""

    def test_load_and_transform(self) -> None:
        """Test loading a template with marker transformation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "prompt.j2"
            template_path.write_text(
                """{#jt:anchor:system#}
System prompt

{#jt:anchor:user#}
{{ user_input }}"""
            )

            env = Environment(loader=FileSystemLoader(tmpdir))
            inst = instrument(env)

            template = load_template_with_markers(env, "prompt.j2", inst)
            result = template.render({"user_input": "Hello"})

            # The anchors should have been transformed and rendered
            assert "System prompt" in result
            assert "Hello" in result

    def test_load_without_loader_raises(self) -> None:
        """Test that loading without a loader raises an error."""
        env = Environment()  # No loader

        with pytest.raises(ValueError, match="must have a loader"):
            load_template_with_markers(env, "template.j2")


class TestRealWorldScenarios:
    """Integration tests for real-world usage patterns."""

    def test_llm_prompt_template(self) -> None:
        """Test a realistic LLM prompt template."""
        template = """{#jt:anchor:system#}
You are a helpful AI assistant. Be concise and accurate.

{#jt:anchor:context#}
{% if context %}
{#jt:trace:context_provided#}
Context: {{ context }}
{% endif %}

{#jt:anchor:user#}
User: {{ user_message }}

{% if tools %}
{#jt:trace:tools_available#}
Available tools: {{ tools | join(", ") }}
{% endif %}"""

        spec = TemplateSpec.from_string(template)

        # Test with context and tools
        rendered = spec.render(
            {
                "context": "User prefers short answers",
                "user_message": "What is Python?",
                "tools": ["search", "calculate"],
            }
        )

        assert rendered.has_section("system")
        assert rendered.has_section("context")
        assert rendered.has_section("user")

        assert rendered.has_trace("context_provided")
        assert rendered.has_trace("tools_available")

        assert "helpful AI assistant" in rendered.section("system").text
        assert "User prefers short answers" in rendered.section("context").text
        assert "What is Python?" in rendered.section("user").text

        # Test without context
        rendered = spec.render(
            {
                "context": None,
                "user_message": "Hello",
                "tools": None,
            }
        )

        assert not rendered.has_trace("context_provided")
        assert not rendered.has_trace("tools_available")

    def test_production_vs_test_mode(self) -> None:
        """Test behavior difference between production and test mode."""
        template = "{#jt:anchor:content#}Hello {{ name }}"

        # Test mode (default) - markers are transformed
        test_spec = TemplateSpec.from_string(template, test_mode=True)
        test_rendered = test_spec.render({"name": "World"})
        assert test_rendered.has_section("content")

        # Production mode - markers not transformed, but comment stripped by Jinja
        prod_spec = TemplateSpec.from_string(template, test_mode=False)
        prod_rendered = prod_spec.render({"name": "World"})
        # In production mode, no instrumentation so no sections
        assert not prod_rendered.has_section("content")
        # The content should still be there (comment stripped by Jinja)
        assert "Hello World" in prod_rendered.text
