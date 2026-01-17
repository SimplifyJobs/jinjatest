"""Tests for macro functionality."""

import pytest

from jinjatest import TemplateSpec


class TestMacros:
    """Test macro-as-function functionality."""

    def test_simple_macro(self) -> None:
        """Test calling a simple macro."""
        spec = TemplateSpec.from_string("""
{% macro greet(name) %}
Hello, {{ name }}!
{% endmacro %}
""")

        greet = spec.macro("greet")
        result = greet("World")
        assert "Hello, World!" in result

    def test_macro_with_defaults(self) -> None:
        """Test macro with default arguments."""
        spec = TemplateSpec.from_string("""
{% macro format_price(amount, currency="USD") %}
{{ currency }} {{ amount }}
{% endmacro %}
""")

        format_price = spec.macro("format_price")

        assert "USD 100" in format_price(100)
        assert "EUR 50" in format_price(50, "EUR")

    def test_macro_with_conditionals(self) -> None:
        """Test macro with conditional logic."""
        spec = TemplateSpec.from_string("""
{% macro status_badge(status) %}
{% if status == "active" %}
[ACTIVE]
{% elif status == "pending" %}
[PENDING]
{% else %}
[UNKNOWN]
{% endif %}
{% endmacro %}
""")

        status_badge = spec.macro("status_badge")

        assert "ACTIVE" in status_badge("active")
        assert "PENDING" in status_badge("pending")
        assert "UNKNOWN" in status_badge("other")

    def test_macro_not_found(self) -> None:
        """Test that missing macro raises AttributeError."""
        spec = TemplateSpec.from_string("{% macro exists() %}{% endmacro %}")

        with pytest.raises(AttributeError) as exc_info:
            spec.macro("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_prompt_builder_macro(self) -> None:
        """Test using macros as prompt builders (dbt-style)."""
        spec = TemplateSpec.from_string("""
{% macro build_prompt(user_input, context=None) %}
{% set parts = [] %}
{% do parts.append("You are a helpful assistant.") %}
{% do parts.append("User: " ~ user_input) %}
{% if context %}
{% do parts.append("Context: " ~ context) %}
{% endif %}
{{ parts | join("\n") }}
{% endmacro %}
""")

        build_prompt = spec.macro("build_prompt")

        # Without context
        result = build_prompt("Hello")
        assert "helpful assistant" in result
        assert "User: Hello" in result
        assert "Context:" not in result

        # With context
        result = build_prompt("Hello", context="Some background")
        assert "Context: Some background" in result

    def test_macro_returning_list(self) -> None:
        """Test macro that builds and returns a list (for structured output)."""
        spec = TemplateSpec.from_string("""
{% macro build_messages(role, content) %}
[{"role": "{{ role }}", "content": "{{ content }}"}]
{% endmacro %}
""")

        build_messages = spec.macro("build_messages")
        result = build_messages("user", "Hello!")

        # Parse as JSON to verify structure
        import json

        messages = json.loads(result.strip())
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
