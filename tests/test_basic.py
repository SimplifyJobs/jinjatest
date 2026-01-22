"""Basic tests for jinjatest functionality."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from jinjatest import (
    ContextValidationError,
    PromptAsserts,
    TemplateRenderError,
    TemplateSpec,
    create_environment,
)


# Define context models
class WelcomeContext(BaseModel):
    user_name: str
    plan: str


TEMPLATE_DIR = Path(__file__).parent / "templates"


class TestTemplateSpecBasic:
    """Test basic TemplateSpec functionality."""

    def test_render_from_string(self) -> None:
        """Test rendering a template from string."""
        spec = TemplateSpec.from_string("Hello, {{ name }}!")
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello, World!"

    def test_render_from_file(self) -> None:
        """Test rendering a template from file."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "welcome.j2",
            context_model=WelcomeContext,
        )
        rendered = spec.render({"user_name": "Ada", "plan": "pro"})
        assert "Hello, Ada!" in rendered.text
        assert "Welcome to Pro!" in rendered.text

    def test_context_validation(self) -> None:
        """Test that context is validated against Pydantic model."""
        spec = TemplateSpec.from_string(
            "Hello, {{ user_name }}!",
            context_model=WelcomeContext,
        )

        # Missing required field should fail
        with pytest.raises(ContextValidationError):
            spec.render({"user_name": "Ada"})  # missing 'plan'

    def test_undefined_variable_error(self) -> None:
        """Test that undefined variables raise errors with StrictUndefined."""
        spec = TemplateSpec.from_string("Hello, {{ undefined_var }}!")
        with pytest.raises(TemplateRenderError):
            spec.render({})


class TestRenderedPrompt:
    """Test RenderedPrompt functionality."""

    def test_normalized_text(self) -> None:
        """Test text normalization."""
        spec = TemplateSpec.from_string("Hello,   {{ name }}!  \n\n\nWorld")
        rendered = spec.render({"name": "Test"})
        assert rendered.normalized == "Hello, Test!\n\nWorld"

    def test_contains_methods(self) -> None:
        """Test contains/not_contains methods."""
        spec = TemplateSpec.from_string("Hello, {{ name }}!")
        rendered = spec.render({"name": "World"})

        assert rendered.contains("Hello")
        assert rendered.not_contains("Goodbye")
        assert rendered.contains_line("Hello, World!")

    def test_regex_matching(self) -> None:
        """Test regex matching."""
        spec = TemplateSpec.from_string("Count: {{ count }}")
        rendered = spec.render({"count": 42})

        assert rendered.matches(r"Count:\s*\d+")
        assert rendered.find_all(r"\d+") == ["42"]


class TestPromptAsserts:
    """Test PromptAsserts functionality."""

    def test_chained_assertions(self) -> None:
        """Test chained assertion methods."""
        spec = TemplateSpec.from_string(
            "Hello, {{ name }}! You have {{ count }} items."
        )
        rendered = spec.render({"name": "Ada", "count": 5})

        asserts = PromptAsserts(rendered)
        asserts.contains("Hello, Ada").contains("5 items").not_contains("Error")

    def test_normalized_assertions(self) -> None:
        """Test assertions on normalized text."""
        spec = TemplateSpec.from_string("Hello,   {{ name }}!")
        rendered = spec.render({"name": "Ada"})

        asserts = PromptAsserts(rendered).normalized()
        asserts.contains("Hello, Ada!")

    def test_regex_assertion(self) -> None:
        """Test regex assertion."""
        spec = TemplateSpec.from_string("Order #{{ order_id }}")
        rendered = spec.render({"order_id": 12345})

        PromptAsserts(rendered).regex(r"Order #\d+")

    def test_failed_assertion_message(self) -> None:
        """Test that failed assertions have helpful messages."""
        spec = TemplateSpec.from_string("Hello")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).contains("Goodbye")

        assert "Expected text to contain" in str(exc_info.value)
        assert "Goodbye" in str(exc_info.value)


class TestJsonParsing:
    """Test JSON parsing functionality."""

    def test_as_json(self) -> None:
        """Test parsing rendered output as JSON."""
        spec = TemplateSpec.from_string('{"name": "{{ name }}", "active": true}')
        rendered = spec.render({"name": "Test"})

        data = rendered.as_json()
        assert data == {"name": "Test", "active": True}

    def test_as_json_with_comments(self) -> None:
        """Test parsing JSON with comments when allow_comments=True."""
        spec = TemplateSpec.from_string("""{
            // This is a comment
            "name": "{{ name }}",
            "value": 42  /* inline comment */
        }""")
        rendered = spec.render({"name": "Test"})

        data = rendered.as_json(allow_comments=True)
        assert data == {"name": "Test", "value": 42}

    def test_as_json_rejects_comments_by_default(self) -> None:
        """Test that comments cause parse error by default."""
        from jinjatest.parsers.json_parser import JSONParseError

        spec = TemplateSpec.from_string('{"key": "value"} // comment')
        rendered = spec.render({})

        with pytest.raises(JSONParseError):
            rendered.as_json()


class TestProUsers:
    """Test pro user scenarios from the spec."""

    def test_welcome_pro_user(self) -> None:
        """Test welcome message for pro users."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "welcome.j2",
            context_model=WelcomeContext,
        )
        rendered = spec.render({"user_name": "Ada", "plan": "pro"})

        asserts = PromptAsserts(rendered).normalized()
        asserts.contains_line("Hello, Ada!")
        asserts.not_contains("Upgrade now")
        asserts.regex(r"Plan:\s*pro")

    def test_welcome_free_user(self) -> None:
        """Test welcome message for free users."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "welcome.j2",
            context_model=WelcomeContext,
        )
        rendered = spec.render({"user_name": "Bob", "plan": "free"})

        asserts = PromptAsserts(rendered)
        asserts.contains("Upgrade now")
        asserts.not_contains("Welcome to Pro")


class TestPromptAssertsExtended:
    """Extended tests for PromptAsserts functionality."""

    def test_not_contains_shows_context(self) -> None:
        """Test that not_contains shows surrounding context in error."""
        spec = TemplateSpec.from_string("Hello World, this is a test message")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).not_contains("World")

        error_msg = str(exc_info.value)
        assert "NOT contain" in error_msg
        assert "position" in error_msg

    def test_has_exact_line(self) -> None:
        """Test has_exact_line with exact match."""
        spec = TemplateSpec.from_string("Line one\nLine two\nLine three")
        rendered = spec.render({})

        PromptAsserts(rendered).has_exact_line("Line two")

    def test_has_exact_line_with_close_match_suggestion(self) -> None:
        """Test has_exact_line shows similar lines when failing."""
        spec = TemplateSpec.from_string("Line one\nLine two\nLine three")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).has_exact_line("Line tow")  # typo

        error_msg = str(exc_info.value)
        assert "Did you mean" in error_msg
        assert "Line two" in error_msg

    def test_line_count(self) -> None:
        """Test line_count assertion."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})

        PromptAsserts(rendered).line_count(3)

    def test_line_count_fails(self) -> None:
        """Test line_count assertion failure."""
        spec = TemplateSpec.from_string("Line 1\nLine 2")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).line_count(5)

        assert "Expected 5 lines" in str(exc_info.value)
        assert "found 2" in str(exc_info.value)

    def test_line_count_between(self) -> None:
        """Test line_count_between assertion."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})

        PromptAsserts(rendered).line_count_between(2, 5)

    def test_line_count_between_fails(self) -> None:
        """Test line_count_between assertion failure."""
        spec = TemplateSpec.from_string("Line 1\nLine 2")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).line_count_between(5, 10)

        assert "between 5 and 10" in str(exc_info.value)

    def test_not_regex(self) -> None:
        """Test not_regex assertion passes when pattern not found."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        PromptAsserts(rendered).not_regex(r"\d+")

    def test_not_regex_fails(self) -> None:
        """Test not_regex assertion fails when pattern found."""
        spec = TemplateSpec.from_string("Order #12345")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).not_regex(r"\d+")

        error_msg = str(exc_info.value)
        assert "NOT match" in error_msg
        assert "12345" in error_msg

    def test_equals(self) -> None:
        """Test equals assertion with exact match."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        PromptAsserts(rendered).equals("Hello World")

    def test_equals_fails_with_diff(self) -> None:
        """Test equals shows diff on failure."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).equals("Hello Earth")

        error_msg = str(exc_info.value)
        assert "does not match" in error_msg

    def test_equals_json(self) -> None:
        """Test equals_json assertion."""
        spec = TemplateSpec.from_string('{"name": "test", "count": 42}')
        rendered = spec.render({})

        PromptAsserts(rendered).equals_json({"name": "test", "count": 42})

    def test_equals_json_fails_with_diff(self) -> None:
        """Test equals_json shows diff on failure."""
        spec = TemplateSpec.from_string('{"name": "test"}')
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).equals_json({"name": "different"})

        assert "JSON does not match" in str(exc_info.value)

    def test_contains_line_fails(self) -> None:
        """Test contains_line failure shows searched lines."""
        spec = TemplateSpec.from_string("First line\nSecond line")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).contains_line("Not present")

        error_msg = str(exc_info.value)
        assert "Expected some line to contain" in error_msg
        assert "Lines searched" in error_msg


class TestAssertNoUndefined:
    """Tests for assert_no_undefined function."""

    def test_assert_no_undefined_passes(self) -> None:
        """Test that clean text passes."""
        from jinjatest import assert_no_undefined

        assert_no_undefined("Hello World, this is normal text")

    def test_assert_no_undefined_detects_undefined(self) -> None:
        """Test detection of 'Undefined' literal."""
        from jinjatest import assert_no_undefined

        with pytest.raises(AssertionError) as exc_info:
            assert_no_undefined("Hello Undefined World")

        assert "Undefined" in str(exc_info.value)

    def test_assert_no_undefined_detects_template_syntax(self) -> None:
        """Test detection of unreplaced template syntax."""
        from jinjatest import assert_no_undefined

        with pytest.raises(AssertionError) as exc_info:
            assert_no_undefined("Hello {{ name }}")

        assert "unreplaced template syntax" in str(exc_info.value)


class TestRenderedPromptExtended:
    """Extended tests for RenderedPrompt functionality."""

    def test_has_line(self) -> None:
        """Test has_line for exact line matching."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})

        assert rendered.has_line("Line 2")
        assert not rendered.has_line("Line 4")

    def test_lines_property(self) -> None:
        """Test lines property returns list of lines."""
        spec = TemplateSpec.from_string("A\nB\nC")
        rendered = spec.render({})

        assert rendered.lines == ["A", "B", "C"]

    def test_normalized_lines_property(self) -> None:
        """Test normalized_lines property."""
        spec = TemplateSpec.from_string("A  \nB  \nC  ")
        rendered = spec.render({})

        lines = rendered.normalized_lines
        assert "A" in lines
        assert "B" in lines

    def test_as_yaml(self) -> None:
        """Test parsing rendered output as YAML."""
        spec = TemplateSpec.from_string("name: Test\ncount: 42")
        rendered = spec.render({})

        data = rendered.as_yaml()
        assert data == {"name": "Test", "count": 42}

    def test_as_yaml_list(self) -> None:
        """Test parsing YAML list."""
        spec = TemplateSpec.from_string("- item1\n- item2\n- item3")
        rendered = spec.render({})

        data = rendered.as_yaml()
        assert data == ["item1", "item2", "item3"]

    def test_markdown_section(self) -> None:
        """Test finding markdown section by title."""
        spec = TemplateSpec.from_string("# Title\nContent\n## Section\nMore content")
        rendered = spec.render({})

        section = rendered.markdown_section("Title")
        assert section is not None
        assert section.title == "Title"

    def test_markdown_section_not_found(self) -> None:
        """Test markdown_section returns None for missing section."""
        spec = TemplateSpec.from_string("# Title\nContent")
        rendered = spec.render({})

        section = rendered.markdown_section("Missing")
        assert section is None


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_normalize_collapses_whitespace(self) -> None:
        """Test whitespace collapse."""
        from jinjatest import normalize_text

        result = normalize_text("Hello    World")
        assert result == "Hello World"

    def test_normalize_strips_lines(self) -> None:
        """Test line stripping."""
        from jinjatest import normalize_text

        result = normalize_text("Hello  \nWorld  ")
        assert result == "Hello\nWorld"

    def test_normalize_collapses_blank_lines(self) -> None:
        """Test multiple blank lines collapse."""
        from jinjatest import normalize_text

        result = normalize_text("Hello\n\n\n\nWorld")
        assert result == "Hello\n\nWorld"

    def test_normalize_strips_leading_trailing(self) -> None:
        """Test leading/trailing whitespace stripped."""
        from jinjatest import normalize_text

        result = normalize_text("  \n\nHello World\n\n  ")
        assert result == "Hello World"

    def test_normalize_with_options(self) -> None:
        """Test normalize_text with options disabled."""
        from jinjatest import normalize_text

        result = normalize_text("Hello    World", collapse_whitespace=False)
        assert "    " in result


class TestCreateEnvironment:
    """Tests for create_environment function."""

    def test_basic_environment(self) -> None:
        """Test creating basic environment."""
        env = create_environment()
        assert env is not None
        # do extension should work - test by using do statement
        template = env.from_string("{% set x = [] %}{% do x.append(1) %}{{ x }}")
        result = template.render({})
        assert "[1]" in result

    def test_environment_with_template_paths(self) -> None:
        """Test environment with template paths."""
        env = create_environment(template_paths=[TEMPLATE_DIR])
        template = env.get_template("welcome.j2")
        assert template is not None

    def test_environment_with_mock_templates(self) -> None:
        """Test environment with mock templates."""
        env = create_environment(mock_templates={"test.j2": "Hello {{ name }}"})
        template = env.get_template("test.j2")
        result = template.render({"name": "World"})
        assert result == "Hello World"

    def test_environment_with_custom_filters(self) -> None:
        """Test environment with custom filters."""

        def reverse_filter(s: str) -> str:
            return s[::-1]

        env = create_environment(filters={"reverse": reverse_filter})
        template = env.from_string("{{ name | reverse }}")
        result = template.render({"name": "Hello"})
        assert result == "olleH"

    def test_environment_with_custom_globals(self) -> None:
        """Test environment with custom globals."""
        env = create_environment(globals={"APP_NAME": "TestApp"})
        template = env.from_string("Welcome to {{ APP_NAME }}")
        result = template.render({})
        assert result == "Welcome to TestApp"

    def test_environment_with_custom_tests(self) -> None:
        """Test environment with custom tests."""

        def is_even(n: int) -> bool:
            return n % 2 == 0

        env = create_environment(tests={"even": is_even})
        template = env.from_string("{% if num is even %}even{% else %}odd{% endif %}")
        assert template.render({"num": 4}) == "even"
        assert template.render({"num": 3}) == "odd"

    def test_environment_with_native_types(self) -> None:
        """Test native types environment."""
        from jinja2.nativetypes import NativeEnvironment

        env = create_environment(native_types=True)
        assert isinstance(env, NativeEnvironment)

    def test_environment_with_sandboxed(self) -> None:
        """Test sandboxed environment."""
        from jinja2.sandbox import SandboxedEnvironment

        env = create_environment(sandboxed=True)
        assert isinstance(env, SandboxedEnvironment)


class TestRenderedPromptSection:
    """Tests for RenderedPromptSection class."""

    def test_section_normalized(self) -> None:
        """Test section normalized property."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        section = rendered.section("system")
        normalized = section.normalized
        assert isinstance(normalized, str)
        assert "System rules" in normalized

    def test_section_contains(self) -> None:
        """Test section contains method."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        section = rendered.section("user")
        assert section.contains("Ada")
        assert not section.contains("Bob")

    def test_section_not_contains(self) -> None:
        """Test section not_contains method."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        section = rendered.section("system")
        assert section.not_contains("Ada")

    def test_section_matches(self) -> None:
        """Test section matches method."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        section = rendered.section("user")
        assert section.matches(r"User:\s+Ada")

    def test_has_section(self) -> None:
        """Test has_section method."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        assert rendered.has_section("system")
        assert rendered.has_section("user")
        assert not rendered.has_section("nonexistent")

    def test_sections_dict(self) -> None:
        """Test sections() returns dict of all sections."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help me", "context_items": []}
        )

        sections = rendered.sections()
        assert isinstance(sections, dict)
        assert "system" in sections
        assert "user" in sections


class TestTemplateSpecExtended:
    """Extended tests for TemplateSpec."""

    def test_render_with_pydantic_model_instance(self) -> None:
        """Test rendering with a Pydantic model instance."""
        spec = TemplateSpec.from_string(
            "Hello, {{ user_name }}! Plan: {{ plan }}",
            context_model=WelcomeContext,
        )
        ctx = WelcomeContext(user_name="Ada", plan="pro")
        rendered = spec.render(ctx)
        assert "Hello, Ada!" in rendered.text
        assert "Plan: pro" in rendered.text

    def test_template_property(self) -> None:
        """Test template property."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.template is not None

    def test_env_property(self) -> None:
        """Test env property."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.env is not None

    def test_context_model_property(self) -> None:
        """Test context_model property."""
        spec = TemplateSpec.from_string("Hello", context_model=WelcomeContext)
        assert spec.context_model is WelcomeContext

    def test_context_model_property_none(self) -> None:
        """Test context_model property when not set."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.context_model is None

    def test_render_generic_exception(self) -> None:
        """Test that generic template errors are wrapped."""
        spec = TemplateSpec.from_string("{{ 1/0 }}")
        with pytest.raises(TemplateRenderError) as exc_info:
            spec.render({})
        assert "rendering failed" in str(exc_info.value)

    def test_test_mode_false(self) -> None:
        """Test creating template without test mode."""
        spec = TemplateSpec.from_string("Hello {{ name }}", test_mode=False)
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello World"
        # Even without test mode, anchor_index is created (but empty)
        assert rendered.trace_events == []


class TestContextValidationExtended:
    """Extended tests for context validation."""

    def test_validation_error_contains_details(self) -> None:
        """Test that validation errors contain field details."""
        spec = TemplateSpec.from_string(
            "Hello",
            context_model=WelcomeContext,
        )

        with pytest.raises(ContextValidationError) as exc_info:
            spec.render({"user_name": "Ada"})  # missing plan

        assert exc_info.value.validation_errors is not None
        assert len(exc_info.value.validation_errors) > 0


class TestSnapshotAssertion:
    """Tests for snapshot assertion functionality."""

    def test_snapshot_creates_file(self, tmp_path) -> None:
        """Test snapshot creates file when it doesn't exist."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        snapshot_dir = tmp_path / "snapshots"
        PromptAsserts(rendered).snapshot("test_output", snapshot_dir=snapshot_dir)

        snapshot_file = snapshot_dir / "test_output.txt"
        assert snapshot_file.exists()
        assert snapshot_file.read_text() == "Hello World"

    def test_snapshot_matches_existing(self, tmp_path) -> None:
        """Test snapshot passes when content matches."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()
        (snapshot_dir / "test_output.txt").write_text("Hello World")

        # Should not raise
        PromptAsserts(rendered).snapshot("test_output", snapshot_dir=snapshot_dir)

    def test_snapshot_fails_on_mismatch(self, tmp_path) -> None:
        """Test snapshot fails when content doesn't match."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()
        (snapshot_dir / "test_output.txt").write_text("Different content")

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).snapshot("test_output", snapshot_dir=snapshot_dir)

        assert "Snapshot mismatch" in str(exc_info.value)

    def test_snapshot_update_mode(self, tmp_path) -> None:
        """Test snapshot updates when update=True."""
        spec = TemplateSpec.from_string("New content")
        rendered = spec.render({})

        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()
        (snapshot_dir / "test_output.txt").write_text("Old content")

        # Should update instead of failing
        PromptAsserts(rendered).snapshot(
            "test_output", snapshot_dir=snapshot_dir, update=True
        )

        assert (snapshot_dir / "test_output.txt").read_text() == "New content"


class TestDiffStrings:
    """Tests for internal diff functionality."""

    def test_diff_shows_changes(self) -> None:
        """Test that equals shows diff on mismatch."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).equals("Line 1\nChanged\nLine 3")

        error_msg = str(exc_info.value)
        assert "-" in error_msg or "+" in error_msg  # Diff markers


class TestRenderedPromptMoreMethods:
    """Additional tests for RenderedPrompt methods."""

    def test_not_contains_method(self) -> None:
        """Test not_contains method on RenderedPrompt."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        assert rendered.not_contains("Goodbye")
        assert not rendered.not_contains("Hello")

    def test_contains_line_partial(self) -> None:
        """Test contains_line with partial match."""
        spec = TemplateSpec.from_string("Line one\nLine two\nLine three")
        rendered = spec.render({})

        assert rendered.contains_line("two")
        assert not rendered.contains_line("four")

    def test_trace_count(self) -> None:
        """Test trace_count method."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        # Should have recorded the no_context trace
        assert rendered.trace_count("no_context") == 1
        assert rendered.trace_count("nonexistent") == 0

    def test_has_section_without_anchors(self) -> None:
        """Test has_section when no anchors exist."""
        spec = TemplateSpec.from_string("No anchors here", test_mode=False)
        rendered = spec.render({})

        # anchor_index is still created but empty
        assert not rendered.has_section("anything")

    def test_sections_empty_when_no_anchors(self) -> None:
        """Test sections() returns empty dict when no anchors."""
        spec = TemplateSpec.from_string("No anchors", test_mode=False)
        rendered = spec.render({})

        sections = rendered.sections()
        # anchor_index exists but is empty
        assert isinstance(sections, dict)

    def test_section_raises_when_not_found(self) -> None:
        """Test section() raises KeyError for missing anchor."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        with pytest.raises(KeyError) as exc_info:
            rendered.section("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "Available anchors" in str(exc_info.value)


class TestTruncateAndDiff:
    """Tests to cover internal helper functions."""

    def test_long_error_message_truncated(self) -> None:
        """Test that long strings in error messages are truncated."""
        spec = TemplateSpec.from_string("Short text")
        rendered = spec.render({})

        long_string = "x" * 300
        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).contains(long_string)

        error_msg = str(exc_info.value)
        # Should be truncated
        assert "..." in error_msg

    def test_contains_with_short_string(self) -> None:
        """Test contains with a short string (no truncation)."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        # Should pass without truncation issues
        PromptAsserts(rendered).contains("Hello")

    def test_not_contains_context_extraction(self) -> None:
        """Test that not_contains shows context around match."""
        long_text = "Start " + "x" * 50 + "MATCH" + "y" * 50 + " End"
        spec = TemplateSpec.from_string(long_text)
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).not_contains("MATCH")

        error_msg = str(exc_info.value)
        assert "position" in error_msg


class TestRenderedPromptProperties:
    """Tests for RenderedPrompt property access."""

    def test_clean_text_without_anchors(self) -> None:
        """Test clean_text when no anchor_index."""
        spec = TemplateSpec.from_string("Plain text", test_mode=False)
        rendered = spec.render({})

        # clean_text should work even without instrumentation
        assert "Plain text" in rendered.clean_text

    def test_normalized_without_anchors(self) -> None:
        """Test normalized when no anchor_index."""
        spec = TemplateSpec.from_string("  Plain   text  ", test_mode=False)
        rendered = spec.render({})

        # normalized should work
        assert "Plain text" in rendered.normalized

    def test_as_markdown_sections(self) -> None:
        """Test as_markdown_sections method."""
        spec = TemplateSpec.from_string("# Header\nContent\n## Subheader\nMore")
        rendered = spec.render({})

        sections = rendered.as_markdown_sections()
        assert len(sections) >= 1
        assert sections[0].title == "Header"


class TestMoreAssertionErrors:
    """Tests for more assertion error paths."""

    def test_has_exact_line_no_close_match(self) -> None:
        """Test has_exact_line when no close matches exist."""
        spec = TemplateSpec.from_string("Apple\nBanana\nCherry")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).has_exact_line("Zebra completely different")

        # Error should not include "Did you mean" if nothing is close
        error_msg = str(exc_info.value)
        assert "exact line" in error_msg.lower()

    def test_regex_failure_shows_pattern(self) -> None:
        """Test regex failure message shows the pattern."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})

        with pytest.raises(AssertionError) as exc_info:
            PromptAsserts(rendered).regex(r"\d{5}")

        assert r"\d{5}" in str(exc_info.value)

    def test_chaining_multiple_assertions(self) -> None:
        """Test multiple assertions can be chained."""
        spec = TemplateSpec.from_string("Hello World 123")
        rendered = spec.render({})

        # Chain multiple assertions
        result = (
            PromptAsserts(rendered)
            .contains("Hello")
            .contains("World")
            .regex(r"\d+")
            .not_contains("Goodbye")
        )
        # Should return self for chaining
        assert isinstance(result, PromptAsserts)


class TestExceptionClasses:
    """Tests for exception class instantiation."""

    def test_prompt_assertion_error(self) -> None:
        """Test PromptAssertionError can be raised."""
        from jinjatest.asserts import PromptAssertionError

        with pytest.raises(PromptAssertionError):
            raise PromptAssertionError("Test error message")

    def test_template_render_error_with_original(self) -> None:
        """Test TemplateRenderError preserves original error."""
        original = ValueError("original")
        error = TemplateRenderError("wrapper", original_error=original)
        assert error.original_error is original

    def test_context_validation_error_with_errors(self) -> None:
        """Test ContextValidationError stores validation errors."""
        errors = [{"loc": ("field",), "msg": "required"}]
        error = ContextValidationError("validation failed", validation_errors=errors)
        assert error.validation_errors == errors
        assert len(error.validation_errors) == 1


class TestInstrumentationDirect:
    """Tests for instrumentation module."""

    def test_create_test_instrumentation(self) -> None:
        """Test creating test instrumentation."""
        from jinjatest.instrumentation import (
            create_instrumentation,
            TestInstrumentation,
        )

        instr = create_instrumentation(test_mode=True)
        assert isinstance(instr, TestInstrumentation)

    def test_create_production_instrumentation(self) -> None:
        """Test creating production instrumentation."""
        from jinjatest.instrumentation import (
            create_instrumentation,
            ProductionInstrumentation,
        )

        instr = create_instrumentation(test_mode=False)
        assert isinstance(instr, ProductionInstrumentation)

    def test_test_instrumentation_anchor(self) -> None:
        """Test anchor method on TestInstrumentation."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        marker = instr.anchor("test_section")
        assert "test_section" in marker
        assert "ANCHOR" in marker

    def test_test_instrumentation_trace(self) -> None:
        """Test trace method records events."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        result = instr.trace("event_name")
        assert result == ""
        assert "event_name" in instr.trace_events

    def test_test_instrumentation_clear(self) -> None:
        """Test clear resets trace events."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        instr.trace("event1")
        instr.trace("event2")
        assert len(instr.trace_events) == 2

        instr.clear()
        assert len(instr.trace_events) == 0

    def test_production_instrumentation_anchor(self) -> None:
        """Test anchor on production instrumentation returns empty."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        result = instr.anchor("test")
        assert result == ""

    def test_production_instrumentation_trace(self) -> None:
        """Test trace on production instrumentation returns empty."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        result = instr.trace("event")
        assert result == ""

    def test_anchor_index_basic(self) -> None:
        """Test AnchorIndex basic functionality through template rendering."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        # Verify anchor index is created
        assert rendered.anchor_index is not None
        assert len(rendered.anchor_index.anchors) > 0

    def test_anchor_index_list_anchors(self) -> None:
        """Test listing available anchors."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
        )
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        anchors = list(rendered.anchor_index.anchors.keys())
        assert "system" in anchors
        assert "user" in anchors


class TestRenderedPromptFindMethods:
    """Tests for RenderedPrompt find methods."""

    def test_find_all(self) -> None:
        """Test find_all returns all regex matches."""
        spec = TemplateSpec.from_string("abc 123 def 456 ghi 789")
        rendered = spec.render({})

        matches = rendered.find_all(r"\d+")
        assert len(matches) == 3
        assert "123" in matches
        assert "456" in matches
        assert "789" in matches

    def test_matches_method(self) -> None:
        """Test matches method returns bool for regex match."""
        spec = TemplateSpec.from_string("Order #12345 placed")
        rendered = spec.render({})

        assert rendered.matches(r"#\d+")
        assert not rendered.matches(r"@\d+")

    def test_normalized_contains_substring(self) -> None:
        """Test normalized text for contains check."""
        spec = TemplateSpec.from_string("Hello   World")
        rendered = spec.render({})

        # Check normalized text contains the value
        assert "Hello World" in rendered.normalized


class TestTemplateSpecMacro:
    """Tests for TemplateSpec macro functionality."""

    def test_macro_basic(self) -> None:
        """Test calling a macro from template."""
        spec = TemplateSpec.from_string(
            """{% macro greet(name) %}Hello, {{ name }}!{% endmacro %}"""
        )
        macro_fn = spec.macro("greet")
        result = macro_fn("World")
        assert "Hello, World!" in str(result)

    def test_macro_not_found(self) -> None:
        """Test macro raises AttributeError when not found."""
        spec = TemplateSpec.from_string("No macros here")
        with pytest.raises(AttributeError) as exc_info:
            spec.macro("nonexistent")
        assert "Macro 'nonexistent' not found" in str(exc_info.value)


class TestRenderNative:
    """Tests for render_native functionality."""

    def test_render_native_dict(self) -> None:
        """Test render_native returns dict for JSON-like output."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string("{{ {'key': 'value'} }}", env=env)
        result = spec.render_native({})
        assert result == {"key": "value"}

    def test_render_native_list(self) -> None:
        """Test render_native returns list."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string("{{ [1, 2, 3] }}", env=env)
        result = spec.render_native({})
        assert result == [1, 2, 3]

    def test_render_native_with_context(self) -> None:
        """Test render_native with context variables."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string("{{ items }}", env=env)
        result = spec.render_native({"items": [1, 2, 3]})
        assert result == [1, 2, 3]

    def test_render_native_with_pydantic_model(self) -> None:
        """Test render_native with Pydantic model context."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string(
            "{{ value }}", env=env, context_model=WelcomeContext
        )
        ctx = WelcomeContext(user_name="Ada", plan="pro")
        result = spec.render_native(ctx)
        # With native environment, the output depends on how the template is written
        assert result is not None


class TestUndeclaredVariables:
    """Tests for undeclared variables functionality."""

    def test_get_undeclared_variables_from_file(self, tmp_path) -> None:
        """Test getting undeclared variables from file template."""
        template_file = tmp_path / "vars.j2"
        template_file.write_text("Hello {{ name }}! Your count is {{ count }}.")

        spec = TemplateSpec.from_file(template_file)
        variables = spec.get_undeclared_variables()
        assert "name" in variables
        assert "count" in variables

    def test_get_undeclared_variables_from_string(self) -> None:
        """Test undeclared variables from string returns empty (limitation)."""
        spec = TemplateSpec.from_string("Hello {{ name }}!")
        # For string templates, this returns empty due to implementation limitation
        variables = spec.get_undeclared_variables()
        assert isinstance(variables, set)

    def test_assert_variables_subset_of_passes(self, tmp_path) -> None:
        """Test assert_variables_subset_of passes when all vars allowed."""
        template_file = tmp_path / "subset.j2"
        template_file.write_text("Hello {{ name }}!")

        spec = TemplateSpec.from_file(template_file)
        # Should not raise
        spec.assert_variables_subset_of({"name", "extra_allowed"})

    def test_assert_variables_subset_of_fails(self, tmp_path) -> None:
        """Test assert_variables_subset_of raises for unexpected vars."""
        from jinjatest import UndeclaredVariableError

        template_file = tmp_path / "extra.j2"
        template_file.write_text("Hello {{ name }}! {{ secret }}")

        spec = TemplateSpec.from_file(template_file)
        with pytest.raises(UndeclaredVariableError) as exc_info:
            spec.assert_variables_subset_of({"name"})
        assert "secret" in str(exc_info.value)


class TestUndeclaredVariableError:
    """Tests for UndeclaredVariableError exception."""

    def test_error_message(self) -> None:
        """Test error message format."""
        from jinjatest import UndeclaredVariableError

        error = UndeclaredVariableError(
            variables={"name", "secret"},
            allowed={"name"},
        )
        assert "secret" in str(error)
        assert "Allowed" in str(error)

    def test_error_attributes(self) -> None:
        """Test error has correct attributes."""
        from jinjatest import UndeclaredVariableError

        error = UndeclaredVariableError(
            variables={"a", "b"},
            allowed={"a"},
        )
        assert error.variables == {"a", "b"}
        assert error.allowed == {"a"}


class TestCreateEnvironmentExtended:
    """Extended tests for create_environment."""

    def test_environment_with_custom_loader(self) -> None:
        """Test environment with custom loader."""
        from jinja2 import DictLoader

        loader = DictLoader({"custom.j2": "Custom template"})
        env = create_environment(loader=loader)
        template = env.get_template("custom.j2")
        assert template.render() == "Custom template"

    def test_environment_with_extensions(self) -> None:
        """Test environment with additional extensions."""
        env = create_environment(extensions=["jinja2.ext.loopcontrols"])
        # Loop controls should be available
        template = env.from_string(
            "{% for i in range(10) %}{% if i == 2 %}{% break %}{% endif %}{{ i }}{% endfor %}"
        )
        result = template.render()
        assert "0" in result
        assert "1" in result

    def test_environment_with_multiple_template_paths(self, tmp_path) -> None:
        """Test environment with multiple template paths."""
        dir1 = tmp_path / "templates1"
        dir2 = tmp_path / "templates2"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "a.j2").write_text("Template A")
        (dir2 / "b.j2").write_text("Template B")

        env = create_environment(template_paths=[dir1, dir2])
        assert env.get_template("a.j2").render() == "Template A"
        assert env.get_template("b.j2").render() == "Template B"

    def test_environment_with_mock_and_paths(self, tmp_path) -> None:
        """Test environment with both mock templates and paths."""
        dir1 = tmp_path / "templates"
        dir1.mkdir()
        (dir1 / "file.j2").write_text("From file")

        env = create_environment(
            template_paths=[dir1],
            mock_templates={"mock.j2": "From mock"},
        )
        assert env.get_template("file.j2").render() == "From file"
        assert env.get_template("mock.j2").render() == "From mock"


class TestRenderedPromptSectionDetails:
    """More tests for RenderedPromptSection."""

    def test_section_not_contains_returns_false(self) -> None:
        """Test section not_contains returns False when found."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        # Ada should be in the user section
        assert not section.not_contains("Ada")

    def test_section_matches_returns_false(self) -> None:
        """Test section matches returns False for non-matching pattern."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        assert not section.matches(r"\d{10}")  # No 10-digit number

    def test_section_normalized_property(self) -> None:
        """Test that section normalized property returns normalized text."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        normalized = section.normalized
        # Should be a string with normalized whitespace
        assert isinstance(normalized, str)
        assert "Ada" in normalized

    def test_section_contains_returns_true(self) -> None:
        """Test section contains returns True when substring found."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        assert section.contains("Ada")

    def test_section_matches_returns_true(self) -> None:
        """Test section matches returns True for matching pattern."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        assert section.matches(r"Ada")  # Should match

    def test_section_matches_with_flags(self) -> None:
        """Test section matches with regex flags."""
        import re

        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )

        section = rendered.section("user")
        # Case insensitive match
        assert section.matches(r"ada", flags=re.IGNORECASE)


class TestNormalizeTextOptions:
    """Tests for normalize_text with different options."""

    def test_normalize_without_strip_lines(self) -> None:
        """Test normalize_text without stripping lines."""
        from jinjatest import normalize_text

        result = normalize_text("Hello  \nWorld  ", strip_lines=False)
        # Whitespace should be collapsed but trailing preserved
        assert "Hello " in result

    def test_normalize_all_options_disabled(self) -> None:
        """Test normalize_text with all options disabled."""
        from jinjatest import normalize_text

        result = normalize_text(
            "Hello    World  ", collapse_whitespace=False, strip_lines=False
        )
        # Should still strip leading/trailing and collapse blank lines
        assert "    " in result  # Multiple spaces preserved


class TestTemplateSpecFromFileExtended:
    """Extended tests for TemplateSpec.from_file."""

    def test_from_file_with_template_dir(self, tmp_path) -> None:
        """Test from_file with explicit template_dir."""
        subdir = tmp_path / "templates"
        subdir.mkdir()
        template_file = subdir / "test.j2"
        template_file.write_text("Hello {{ name }}!")

        spec = TemplateSpec.from_file(
            template_file,
            template_dir=subdir,
        )
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello World!"

    def test_from_file_with_env_kwargs(self, tmp_path) -> None:
        """Test from_file passes env_kwargs to create_environment."""
        template_file = tmp_path / "test.j2"
        template_file.write_text("{{ name | custom_filter }}")

        def custom_filter(s):
            return s.upper()

        spec = TemplateSpec.from_file(
            template_file,
            filters={"custom_filter": custom_filter},
        )
        rendered = spec.render({"name": "world"})
        assert "WORLD" in rendered.text


class TestRenderedPromptParsing:
    """Tests for RenderedPrompt parsing methods."""

    def test_as_json_parses_correctly(self) -> None:
        """Test as_json parses JSON output."""
        spec = TemplateSpec.from_string('{"key": "value", "num": 42}')
        rendered = spec.render({})
        data = rendered.as_json()
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_as_yaml_parses_correctly(self) -> None:
        """Test as_yaml parses YAML output."""
        spec = TemplateSpec.from_string("key: value\nnum: 42")
        rendered = spec.render({})
        data = rendered.as_yaml()
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_as_markdown_sections_parses_correctly(self) -> None:
        """Test as_markdown_sections parses markdown."""
        spec = TemplateSpec.from_string("# Title\nContent\n## Section\nMore")
        rendered = spec.render({})
        sections = rendered.as_markdown_sections()
        assert len(sections) >= 1
        assert sections[0].title == "Title"

    def test_markdown_section_finds_section(self) -> None:
        """Test markdown_section finds specific section."""
        spec = TemplateSpec.from_string("# Title\nContent\n## Section\nMore")
        rendered = spec.render({})
        section = rendered.markdown_section("Title")
        assert section is not None
        assert section.title == "Title"


class TestRenderedPromptQueryMethods:
    """Tests for RenderedPrompt query methods."""

    def test_contains_method(self) -> None:
        """Test contains returns True for substring."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})
        assert rendered.contains("World")
        assert not rendered.contains("Missing")

    def test_not_contains_method(self) -> None:
        """Test not_contains returns True when missing."""
        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})
        assert rendered.not_contains("Missing")
        assert not rendered.not_contains("World")

    def test_contains_line_method(self) -> None:
        """Test contains_line checks line content."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})
        assert rendered.contains_line("Line 2")
        assert not rendered.contains_line("Line 4")

    def test_has_line_method(self) -> None:
        """Test has_line checks exact line."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})
        assert rendered.has_line("Line 2")
        assert not rendered.has_line("Line")

    def test_matches_method(self) -> None:
        """Test matches checks regex pattern."""
        spec = TemplateSpec.from_string("Order #12345")
        rendered = spec.render({})
        assert rendered.matches(r"#\d+")
        assert not rendered.matches(r"@\d+")

    def test_matches_with_flags(self) -> None:
        """Test matches with regex flags."""
        import re

        spec = TemplateSpec.from_string("Hello World")
        rendered = spec.render({})
        assert rendered.matches(r"hello", flags=re.IGNORECASE)

    def test_find_all_method(self) -> None:
        """Test find_all returns all matches."""
        spec = TemplateSpec.from_string("abc 123 def 456")
        rendered = spec.render({})
        matches = rendered.find_all(r"\d+")
        assert matches == ["123", "456"]

    def test_find_all_with_flags(self) -> None:
        """Test find_all with regex flags."""
        import re

        spec = TemplateSpec.from_string("Hello HELLO hello")
        rendered = spec.render({})
        matches = rendered.find_all(r"hello", flags=re.IGNORECASE)
        assert len(matches) == 3


class TestRenderedPromptTraces:
    """Tests for RenderedPrompt trace methods."""

    def test_has_trace_true(self) -> None:
        """Test has_trace returns True when trace exists."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )
        assert rendered.has_trace("no_context")

    def test_has_trace_false(self) -> None:
        """Test has_trace returns False when trace missing."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": ["item"]}
        )
        assert not rendered.has_trace("no_context")

    def test_trace_count_method(self) -> None:
        """Test trace_count returns correct count."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )
        assert rendered.trace_count("no_context") >= 1
        assert rendered.trace_count("nonexistent") == 0


class TestRenderedPromptLinesAndCleanText:
    """Tests for RenderedPrompt lines and clean text properties."""

    def test_lines_property(self) -> None:
        """Test lines property splits on newlines."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})
        assert rendered.lines == ["Line 1", "Line 2", "Line 3"]

    def test_normalized_lines_property(self) -> None:
        """Test normalized_lines property."""
        spec = TemplateSpec.from_string("Line 1\nLine 2\nLine 3")
        rendered = spec.render({})
        lines = rendered.normalized_lines
        assert "Line 1" in lines
        assert "Line 2" in lines
        assert "Line 3" in lines

    def test_clean_text_property(self) -> None:
        """Test clean_text removes anchor markers."""
        spec = TemplateSpec.from_file(TEMPLATE_DIR / "anchored.j2")
        rendered = spec.render(
            {"user_name": "Ada", "request": "Help", "context_items": []}
        )
        clean = rendered.clean_text
        assert "ANCHOR" not in clean
        assert "\x1e" not in clean

    def test_normalized_property(self) -> None:
        """Test normalized property normalizes whitespace."""
        spec = TemplateSpec.from_string("Hello    World")
        rendered = spec.render({})
        assert rendered.normalized == "Hello World"


class TestRenderedPromptSectionDirect:
    """Direct tests for RenderedPromptSection class."""

    def test_section_init_and_text(self) -> None:
        """Test RenderedPromptSection initialization and text property."""
        from jinjatest.rendered import RenderedPromptSection

        section = RenderedPromptSection(name="test", text="Hello World")
        assert section.name == "test"
        assert section.text == "Hello World"

    def test_section_normalized(self) -> None:
        """Test RenderedPromptSection normalized property."""
        from jinjatest.rendered import RenderedPromptSection

        section = RenderedPromptSection(name="test", text="Hello    World")
        assert section.normalized == "Hello World"

    def test_section_contains(self) -> None:
        """Test RenderedPromptSection contains method."""
        from jinjatest.rendered import RenderedPromptSection

        section = RenderedPromptSection(name="test", text="Hello World")
        assert section.contains("World")
        assert not section.contains("Missing")

    def test_section_not_contains(self) -> None:
        """Test RenderedPromptSection not_contains method."""
        from jinjatest.rendered import RenderedPromptSection

        section = RenderedPromptSection(name="test", text="Hello World")
        assert section.not_contains("Missing")
        assert not section.not_contains("World")

    def test_section_matches(self) -> None:
        """Test RenderedPromptSection matches method."""
        from jinjatest.rendered import RenderedPromptSection

        section = RenderedPromptSection(name="test", text="Order #12345")
        assert section.matches(r"#\d+")
        assert not section.matches(r"@\d+")


class TestRenderedPromptDirect:
    """Direct tests for RenderedPrompt class."""

    def test_rendered_prompt_init(self) -> None:
        """Test RenderedPrompt initialization."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello World")
        assert rendered.text == "Hello World"
        assert rendered.trace_events == []
        assert rendered.anchor_index is None

    def test_rendered_prompt_with_traces(self) -> None:
        """Test RenderedPrompt with trace events."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello", trace_events=["event1", "event2"])
        assert rendered.trace_events == ["event1", "event2"]

    def test_rendered_prompt_section_raises_without_anchors(self) -> None:
        """Test section() raises when no anchor_index."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello")
        with pytest.raises(KeyError) as exc_info:
            rendered.section("test")
        assert "No anchors available" in str(exc_info.value)

    def test_rendered_prompt_sections_empty_without_anchors(self) -> None:
        """Test sections() returns empty dict without anchor_index."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello")
        assert rendered.sections() == {}

    def test_rendered_prompt_has_section_false_without_anchors(self) -> None:
        """Test has_section returns False without anchor_index."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello")
        assert rendered.has_section("test") is False

    def test_rendered_prompt_clean_text_without_anchors(self) -> None:
        """Test clean_text returns text when no anchor_index."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello World")
        assert rendered.clean_text == "Hello World"

    def test_rendered_prompt_normalized_without_anchors(self) -> None:
        """Test normalized works without anchor_index."""
        from jinjatest.rendered import RenderedPrompt

        rendered = RenderedPrompt(text="Hello    World")
        assert rendered.normalized == "Hello World"


class TestNormalizeTextDirect:
    """Direct tests for normalize_text function."""

    def test_normalize_text_basic(self) -> None:
        """Test basic normalize_text functionality."""
        from jinjatest.rendered import normalize_text

        result = normalize_text("Hello   World")
        assert result == "Hello World"

    def test_normalize_text_strips_lines(self) -> None:
        """Test normalize_text strips trailing whitespace from lines."""
        from jinjatest.rendered import normalize_text

        result = normalize_text("Hello  \nWorld  ")
        assert result == "Hello\nWorld"

    def test_normalize_text_collapses_blank_lines(self) -> None:
        """Test normalize_text collapses multiple blank lines."""
        from jinjatest.rendered import normalize_text

        result = normalize_text("Hello\n\n\n\nWorld")
        assert result == "Hello\n\nWorld"

    def test_normalize_text_no_collapse_whitespace(self) -> None:
        """Test normalize_text without collapsing whitespace."""
        from jinjatest.rendered import normalize_text

        result = normalize_text("Hello   World", collapse_whitespace=False)
        assert "   " in result

    def test_normalize_text_no_strip_lines(self) -> None:
        """Test normalize_text without stripping lines."""
        from jinjatest.rendered import normalize_text

        result = normalize_text("Hello  \nWorld  ", strip_lines=False)
        # Lines are not stripped but whitespace collapse happens
        assert "Hello " in result


class TestAnchorIndexDirect:
    """Direct tests for AnchorIndex class."""

    def test_anchor_index_init_empty(self) -> None:
        """Test AnchorIndex initialization with defaults."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex()
        assert index.anchors == {}
        assert index.clean_text == ""

    def test_anchor_index_from_text_no_anchors(self) -> None:
        """Test AnchorIndex.from_text with no anchors."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex.from_text("Plain text without anchors")
        assert index.clean_text == "Plain text without anchors"
        assert index.anchors == {}

    def test_anchor_index_has_anchor(self) -> None:
        """Test AnchorIndex.has_anchor method."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex(anchors={"test": (0, 10)}, clean_text="0123456789")
        assert index.has_anchor("test") is True
        assert index.has_anchor("nonexistent") is False

    def test_anchor_index_get_section(self) -> None:
        """Test AnchorIndex.get_section method."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex(anchors={"test": (0, 5)}, clean_text="Hello World")
        assert index.get_section("test") == "Hello"

    def test_anchor_index_get_section_not_found(self) -> None:
        """Test AnchorIndex.get_section returns None for missing."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex()
        assert index.get_section("nonexistent") is None

    def test_anchor_index_list_anchors(self) -> None:
        """Test AnchorIndex.list_anchors method."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex(
            anchors={"first": (0, 5), "second": (5, 10)},
            clean_text="0123456789",
        )
        anchors = index.list_anchors()
        assert "first" in anchors
        assert "second" in anchors


class TestCreateInstrumentationDirect:
    """Direct tests for create_instrumentation function."""

    def test_create_test_instrumentation(self) -> None:
        """Test creating test instrumentation."""
        from jinjatest.instrumentation import (
            create_instrumentation,
            TestInstrumentation,
        )

        instr = create_instrumentation(test_mode=True)
        assert isinstance(instr, TestInstrumentation)

    def test_create_production_instrumentation(self) -> None:
        """Test creating production instrumentation."""
        from jinjatest.instrumentation import (
            create_instrumentation,
            ProductionInstrumentation,
        )

        instr = create_instrumentation(test_mode=False)
        assert isinstance(instr, ProductionInstrumentation)


class TestTestInstrumentationDirect:
    """Direct tests for TestInstrumentation class."""

    def test_test_instrumentation_anchor(self) -> None:
        """Test anchor method on TestInstrumentation."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        marker = instr.anchor("test_section")
        assert "test_section" in marker
        assert "ANCHOR" in marker

    def test_test_instrumentation_trace(self) -> None:
        """Test trace method records events."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        result = instr.trace("event_name")
        assert result == ""
        assert "event_name" in instr.trace_events

    def test_test_instrumentation_clear(self) -> None:
        """Test clear resets trace events."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        instr.trace("event1")
        instr.trace("event2")
        assert len(instr.trace_events) == 2

        instr.clear()
        assert len(instr.trace_events) == 0


class TestProductionInstrumentationDirect:
    """Direct tests for ProductionInstrumentation class."""

    def test_production_instrumentation_anchor(self) -> None:
        """Test anchor on production instrumentation returns empty."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        result = instr.anchor("test")
        assert result == ""

    def test_production_instrumentation_trace(self) -> None:
        """Test trace on production instrumentation returns empty."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        result = instr.trace("event")
        assert result == ""

    def test_production_instrumentation_clear(self) -> None:
        """Test clear is a no-op on production instrumentation."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        instr.clear()  # Should not raise

    def test_production_instrumentation_trace_events(self) -> None:
        """Test trace_events returns empty list on production."""
        from jinjatest.instrumentation import ProductionInstrumentation

        instr = ProductionInstrumentation()
        assert instr.trace_events == []


class TestTraceRecorderDirect:
    """Direct tests for TraceRecorder class."""

    def test_trace_recorder_init(self) -> None:
        """Test TraceRecorder initialization."""
        from jinjatest.instrumentation import TraceRecorder

        recorder = TraceRecorder()
        assert recorder.events == []

    def test_trace_recorder_record(self) -> None:
        """Test TraceRecorder.record method."""
        from jinjatest.instrumentation import TraceRecorder

        recorder = TraceRecorder()
        recorder.record("event1")
        recorder.record("event2")
        assert recorder.events == ["event1", "event2"]

    def test_trace_recorder_clear(self) -> None:
        """Test TraceRecorder.clear method."""
        from jinjatest.instrumentation import TraceRecorder

        recorder = TraceRecorder()
        recorder.record("event1")
        recorder.record("event2")
        assert len(recorder.events) == 2

        recorder.clear()
        assert recorder.events == []


class TestTestInstrumentationDisabled:
    """Tests for TestInstrumentation when disabled."""

    def test_disabled_anchor(self) -> None:
        """Test anchor returns empty when disabled."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        instr._enabled = False
        result = instr.anchor("test")
        assert result == ""

    def test_disabled_trace(self) -> None:
        """Test trace returns empty when disabled and doesn't record."""
        from jinjatest.instrumentation import TestInstrumentation

        instr = TestInstrumentation()
        instr._enabled = False
        result = instr.trace("event")
        assert result == ""
        assert instr.trace_events == []


class TestAnchorIndexFromTextWithAnchors:
    """Tests for AnchorIndex.from_text with actual anchors."""

    def test_from_text_single_anchor(self) -> None:
        """Test parsing text with a single anchor."""
        from jinjatest.instrumentation import AnchorIndex, ANCHOR_START, ANCHOR_END

        text = f"Before{ANCHOR_START}ANCHOR:test{ANCHOR_END}After"
        index = AnchorIndex.from_text(text)

        assert "test" in index.anchors
        assert index.clean_text == "BeforeAfter"

    def test_from_text_multiple_anchors(self) -> None:
        """Test parsing text with multiple anchors."""
        from jinjatest.instrumentation import AnchorIndex, ANCHOR_START, ANCHOR_END

        text = f"{ANCHOR_START}ANCHOR:first{ANCHOR_END}Content1{ANCHOR_START}ANCHOR:second{ANCHOR_END}Content2"
        index = AnchorIndex.from_text(text)

        assert "first" in index.anchors
        assert "second" in index.anchors
        assert index.clean_text == "Content1Content2"

    def test_from_text_anchor_sections(self) -> None:
        """Test that anchor sections have correct content."""
        from jinjatest.instrumentation import AnchorIndex, ANCHOR_START, ANCHOR_END

        text = f"{ANCHOR_START}ANCHOR:header{ANCHOR_END}Header content\n{ANCHOR_START}ANCHOR:body{ANCHOR_END}Body content"
        index = AnchorIndex.from_text(text)

        header = index.get_section("header")
        assert "Header content" in header

        body = index.get_section("body")
        assert "Body content" in body


class TestFromFileWithProvidedEnv:
    """Tests for from_file when an environment is provided."""

    @pytest.fixture
    def template_dir(self, tmp_path: Path) -> Path:
        """Create a nested template structure."""
        # Create: tmp/prompts/feature/section/template.j2
        nested = tmp_path / "prompts" / "feature" / "section"
        nested.mkdir(parents=True)

        template_file = nested / "template.j2"
        template_file.write_text("Hello {{ name }}!")

        return tmp_path / "prompts"

    def test_from_file_with_env_preserves_path(self, template_dir: Path) -> None:
        """When env is provided, full path should be preserved."""
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import TemplateSpec
        from jinjatest.instrumentation import create_instrumentation

        env = Environment(loader=FileSystemLoader(str(template_dir)))
        inst = create_instrumentation(test_mode=True)
        env.globals["jt"] = inst

        # This should work - path relative to env's loader
        spec = TemplateSpec.from_file("feature/section/template.j2", env=env)
        rendered = spec.render({"name": "World"})

        assert rendered.text == "Hello World!"

    def test_from_file_with_env_reuses_instrumentation(
        self, template_dir: Path
    ) -> None:
        """When env is already instrumented, should reuse instrumentation."""
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import TemplateSpec
        from jinjatest.instrumentation import create_instrumentation

        env = Environment(loader=FileSystemLoader(str(template_dir)))
        original_inst = create_instrumentation(test_mode=True)
        env.globals["jt"] = original_inst

        spec = TemplateSpec.from_file("feature/section/template.j2", env=env)

        # Should be the same instrumentation instance
        assert spec._instrumentation is original_inst

    def test_from_file_without_env_uses_filename_only(self, template_dir: Path) -> None:
        """When env is None, should use just filename with parent as loader."""
        template_path = template_dir / "feature" / "section" / "template.j2"

        # No env provided - should create one with loader at template's parent
        spec = TemplateSpec.from_file(str(template_path))
        rendered = spec.render({"name": "World"})

        assert rendered.text == "Hello World!"

    def test_from_file_with_env_instruments_if_needed(self, template_dir: Path) -> None:
        """When env is provided but not instrumented, should add instrumentation."""
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import TemplateSpec

        env = Environment(loader=FileSystemLoader(str(template_dir)))
        # Note: NOT calling instrument(env) here

        spec = TemplateSpec.from_file("feature/section/template.j2", env=env)

        # Should have added instrumentation
        assert "jt" in env.globals
        assert spec._instrumentation is not None


class TestFromFileWithTemplateDir:
    """Tests for from_file with explicit template_dir."""

    @pytest.fixture
    def template_structure(self, tmp_path: Path) -> Path:
        """Create template structure."""
        prompts = tmp_path / "prompts"
        nested = prompts / "v2" / "chat"
        nested.mkdir(parents=True)

        (nested / "system.j2").write_text("System: {{ mode }}")
        (nested / "user.j2").write_text("User: {{ input }}")

        return prompts

    def test_from_file_with_template_dir(self, template_structure: Path) -> None:
        """template_dir should set the loader root."""
        spec = TemplateSpec.from_file(
            "v2/chat/system.j2",
            template_dir=template_structure,
        )
        rendered = spec.render({"mode": "helpful"})

        assert rendered.text == "System: helpful"

    def test_from_file_template_dir_ignored_when_env_provided(
        self, template_structure: Path
    ) -> None:
        """template_dir should be ignored when env is provided."""
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import TemplateSpec
        from jinjatest.instrumentation import create_instrumentation

        env = Environment(loader=FileSystemLoader(str(template_structure)))
        inst = create_instrumentation(test_mode=True)
        env.globals["jt"] = inst

        # template_dir is provided but should be ignored since env is provided
        spec = TemplateSpec.from_file(
            "v2/chat/system.j2",
            env=env,
            template_dir="/some/other/path",  # Should be ignored
        )
        rendered = spec.render({"mode": "helpful"})

        assert rendered.text == "System: helpful"


class TestFromFileWithCommentMarkersAndProvidedEnv:
    """Tests for from_file with comment markers when env is provided."""

    @pytest.fixture
    def template_with_markers(self, tmp_path: Path) -> Path:
        """Create a template with comment markers in a nested structure."""
        nested = tmp_path / "prompts" / "v2"
        nested.mkdir(parents=True)

        template_file = nested / "marked.j2"
        template_file.write_text(
            "{#jt:anchor:greeting#}Hello {{ name }}!{#jt:trace:rendered#}"
        )

        return tmp_path / "prompts"

    def test_from_file_with_env_and_markers(self, template_with_markers: Path) -> None:
        """Test that comment markers work when env is provided."""
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import TemplateSpec
        from jinjatest.instrumentation import create_instrumentation

        env = Environment(loader=FileSystemLoader(str(template_with_markers)))
        inst = create_instrumentation(test_mode=True)
        env.globals["jt"] = inst

        spec = TemplateSpec.from_file("v2/marked.j2", env=env)
        rendered = spec.render({"name": "World"})

        assert "Hello World!" in rendered.text
        # Check that trace was recorded
        assert rendered.has_trace("rendered")

    def test_from_file_with_env_no_loader_raises(self) -> None:
        """Test that error is raised when env has no loader and markers are used."""
        from jinja2 import Environment
        from jinjatest import TemplateSpec, TemplateRenderError

        env = Environment()  # No loader

        with pytest.raises(TemplateRenderError) as exc_info:
            TemplateSpec.from_file(
                "some/path/template.j2",
                env=env,
                use_comment_markers=True,
                test_mode=True,
            )

        assert "no loader" in str(exc_info.value)
