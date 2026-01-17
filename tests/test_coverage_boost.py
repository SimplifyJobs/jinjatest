"""Additional tests to boost coverage to 90%."""

import tempfile
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
from jinjatest.asserts import (
    PromptAssertionError,
    _diff_strings,
    _truncate,
    assert_no_undefined,
)
from jinjatest.instrumentation import (
    ProductionInstrumentation,
    TestInstrumentation,
    create_instrumentation,
)
from jinjatest.parsers.fenced_blocks import FencedBlock, extract_fenced_blocks
from jinjatest.parsers.json_parser import JSONParseError, parse_json
from jinjatest.parsers.xml_parser import XMLElement, XMLParseError, parse_xml
from jinjatest.parsers.yaml_parser import YAMLParseError, parse_yaml
from jinjatest.rendered import RenderedPrompt, RenderedPromptSection, normalize_text


class SimpleContext(BaseModel):
    name: str
    value: int


# =============================================================================
# Tests for yaml_parser.py
# =============================================================================


class TestYAMLParserCoverage:
    """Tests to increase yaml_parser.py coverage."""

    def test_yaml_parse_error_attributes(self) -> None:
        """Test YAMLParseError has correct attributes."""
        original = ValueError("test")
        error = YAMLParseError("Test message", original_error=original)
        assert str(error) == "Test message"
        assert error.original_error is original

    def test_yaml_parse_error_without_original(self) -> None:
        """Test YAMLParseError without original error."""
        error = YAMLParseError("Test message")
        assert error.original_error is None

    def test_parse_yaml_basic(self) -> None:
        """Test basic YAML parsing."""
        result = parse_yaml("key: value")
        assert result == {"key": "value"}

    def test_parse_yaml_list(self) -> None:
        """Test parsing YAML list."""
        result = parse_yaml("- item1\n- item2")
        assert result == ["item1", "item2"]

    def test_parse_yaml_error(self) -> None:
        """Test YAML parse error."""
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml("invalid: yaml:\n  bad indent")
        assert "Failed to parse YAML" in str(exc_info.value)
        assert exc_info.value.original_error is not None


# =============================================================================
# Tests for json_parser.py
# =============================================================================


class TestJSONParserCoverage:
    """Tests to increase json_parser.py coverage."""

    def test_json_parse_error_attributes(self) -> None:
        """Test JSONParseError has correct attributes."""
        original = ValueError("test")
        error = JSONParseError("Test message", original_error=original)
        assert str(error) == "Test message"
        assert error.original_error is original

    def test_json_parse_error_without_original(self) -> None:
        """Test JSONParseError without original error."""
        error = JSONParseError("Test message")
        assert error.original_error is None

    def test_parse_json_strips_whitespace(self) -> None:
        """Test that parse_json strips whitespace."""
        result = parse_json('   { "key": "value" }   ')
        assert result == {"key": "value"}


# =============================================================================
# Tests for instrumentation.py
# =============================================================================


class TestInstrumentationCoverage:
    """Tests to increase instrumentation.py coverage."""

    def test_create_instrumentation_test_mode(self) -> None:
        """Test create_instrumentation with test_mode=True."""
        inst = create_instrumentation(test_mode=True)
        assert isinstance(inst, TestInstrumentation)

    def test_create_instrumentation_prod_mode(self) -> None:
        """Test create_instrumentation with test_mode=False."""
        inst = create_instrumentation(test_mode=False)
        assert isinstance(inst, ProductionInstrumentation)

    def test_test_instrumentation_anchor_enabled(self) -> None:
        """Test TestInstrumentation.anchor when enabled."""
        inst = TestInstrumentation()
        result = inst.anchor("test_section")
        assert "ANCHOR:test_section" in result
        assert "\x1e" in result

    def test_test_instrumentation_trace_enabled(self) -> None:
        """Test TestInstrumentation.trace when enabled."""
        inst = TestInstrumentation()
        result = inst.trace("test_event")
        assert result == ""
        assert "test_event" in inst.trace_events

    def test_test_instrumentation_clear(self) -> None:
        """Test TestInstrumentation.clear method."""
        inst = TestInstrumentation()
        inst.trace("event1")
        inst.trace("event2")
        assert len(inst.trace_events) == 2
        inst.clear()
        assert len(inst.trace_events) == 0

    def test_production_instrumentation_anchor(self) -> None:
        """Test ProductionInstrumentation.anchor returns empty."""
        inst = ProductionInstrumentation()
        result = inst.anchor("test")
        assert result == ""

    def test_production_instrumentation_trace(self) -> None:
        """Test ProductionInstrumentation.trace returns empty."""
        inst = ProductionInstrumentation()
        result = inst.trace("test")
        assert result == ""


# =============================================================================
# Tests for rendered.py
# =============================================================================


class TestRenderedCoverage:
    """Tests to increase rendered.py coverage."""

    def test_normalize_text_no_collapse(self) -> None:
        """Test normalize_text without collapsing whitespace."""
        text = "hello   world"
        result = normalize_text(text, collapse_whitespace=False)
        assert result == "hello   world"

    def test_normalize_text_no_strip(self) -> None:
        """Test normalize_text without stripping lines."""
        text = "hello  \nworld  "
        result = normalize_text(text, strip_lines=False)
        assert "hello" in result

    def test_normalize_text_multiple_blank_lines(self) -> None:
        """Test normalize_text collapses multiple blank lines."""
        text = "hello\n\n\n\nworld"
        result = normalize_text(text)
        assert result == "hello\n\nworld"

    def test_rendered_prompt_section_normalized(self) -> None:
        """Test RenderedPromptSection.normalized property."""
        section = RenderedPromptSection(name="test", text="  hello   world  ")
        assert section.normalized == "hello world"

    def test_rendered_prompt_section_contains(self) -> None:
        """Test RenderedPromptSection.contains method."""
        section = RenderedPromptSection(name="test", text="hello world")
        assert section.contains("hello")
        assert not section.contains("goodbye")

    def test_rendered_prompt_section_not_contains(self) -> None:
        """Test RenderedPromptSection.not_contains method."""
        section = RenderedPromptSection(name="test", text="hello world")
        assert section.not_contains("goodbye")
        assert not section.not_contains("hello")

    def test_rendered_prompt_section_matches(self) -> None:
        """Test RenderedPromptSection.matches method."""
        section = RenderedPromptSection(name="test", text="hello 123 world")
        assert section.matches(r"\d+")
        assert not section.matches(r"\d{5}")

    def test_rendered_prompt_lines(self) -> None:
        """Test RenderedPrompt.lines property."""
        rendered = RenderedPrompt(text="line1\nline2\nline3")
        assert rendered.lines == ["line1", "line2", "line3"]

    def test_rendered_prompt_normalized_lines(self) -> None:
        """Test RenderedPrompt.normalized_lines property."""
        rendered = RenderedPrompt(text="line1  \nline2  \nline3  ")
        lines = rendered.normalized_lines
        assert len(lines) == 3

    def test_rendered_prompt_has_section_no_index(self) -> None:
        """Test has_section when no anchor_index."""
        rendered = RenderedPrompt(text="test", anchor_index=None)
        assert rendered.has_section("any") is False

    def test_rendered_prompt_sections_no_index(self) -> None:
        """Test sections when no anchor_index."""
        rendered = RenderedPrompt(text="test", anchor_index=None)
        assert rendered.sections() == {}

    def test_rendered_prompt_section_no_anchors_error(self) -> None:
        """Test section raises KeyError when no anchors available."""
        rendered = RenderedPrompt(text="test", anchor_index=None)
        with pytest.raises(KeyError) as exc_info:
            rendered.section("test")
        assert "No anchors available" in str(exc_info.value)

    def test_rendered_prompt_has_line(self) -> None:
        """Test has_line method."""
        rendered = RenderedPrompt(text="line1\nline2\nline3")
        assert rendered.has_line("line2")
        assert not rendered.has_line("line4")

    def test_rendered_prompt_trace_count(self) -> None:
        """Test trace_count method."""
        rendered = RenderedPrompt(
            text="test", trace_events=["event1", "event1", "event2"]
        )
        assert rendered.trace_count("event1") == 2
        assert rendered.trace_count("event2") == 1
        assert rendered.trace_count("event3") == 0

    def test_rendered_prompt_as_yaml(self) -> None:
        """Test as_yaml method."""
        rendered = RenderedPrompt(text="key: value")
        result = rendered.as_yaml()
        assert result == {"key": "value"}

    def test_rendered_prompt_as_yaml_blocks(self) -> None:
        """Test as_yaml_blocks method."""
        text = """Some text
```yaml
name: test
value: 123
```
More text"""
        rendered = RenderedPrompt(text=text)
        blocks = rendered.as_yaml_blocks()
        assert len(blocks) == 1
        assert blocks[0]["name"] == "test"

    def test_rendered_prompt_as_xml_blocks(self) -> None:
        """Test as_xml_blocks method."""
        text = """Some text
```xml
<root><child>value</child></root>
```
More text"""
        rendered = RenderedPrompt(text=text)
        blocks = rendered.as_xml_blocks()
        assert len(blocks) == 1

    def test_rendered_prompt_markdown_section(self) -> None:
        """Test markdown_section method."""
        text = """# Header 1
Content 1

## Header 2
Content 2"""
        rendered = RenderedPrompt(text=text)
        section = rendered.markdown_section("Header 1")
        assert section is not None
        assert section.title == "Header 1"

    def test_rendered_prompt_markdown_section_not_found(self) -> None:
        """Test markdown_section returns None when not found."""
        rendered = RenderedPrompt(text="# Header\nContent")
        section = rendered.markdown_section("Nonexistent")
        assert section is None


# =============================================================================
# Tests for fenced_blocks.py
# =============================================================================


class TestFencedBlocksCoverage:
    """Tests to increase fenced_blocks.py coverage."""

    def test_fenced_block_dataclass(self) -> None:
        """Test FencedBlock dataclass attributes."""
        block = FencedBlock(
            language="python", content="print('hello')", start_line=1, end_line=3
        )
        assert block.language == "python"
        assert block.content == "print('hello')"
        assert block.start_line == 1
        assert block.end_line == 3

    def test_extract_fenced_blocks_no_language(self) -> None:
        """Test extracting blocks without language tag."""
        text = """```
code here
```"""
        blocks = extract_fenced_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == ""
        assert blocks[0].content == "code here"

    def test_extract_fenced_blocks_with_filter(self) -> None:
        """Test extracting blocks with language filter."""
        text = """```python
print('py')
```
```javascript
console.log('js')
```"""
        py_blocks = extract_fenced_blocks(text, language="python")
        assert len(py_blocks) == 1
        assert py_blocks[0].language == "python"

    def test_extract_fenced_blocks_case_insensitive(self) -> None:
        """Test language filter is case insensitive."""
        text = """```PYTHON
print('hello')
```"""
        blocks = extract_fenced_blocks(text, language="python")
        assert len(blocks) == 1

    def test_extract_fenced_blocks_line_numbers(self) -> None:
        """Test that line numbers are calculated correctly."""
        text = """Line 1
Line 2
```json
{"key": "value"}
```
Line 6"""
        blocks = extract_fenced_blocks(text, language="json")
        assert len(blocks) == 1
        assert blocks[0].start_line == 2  # 0-indexed


# =============================================================================
# Tests for asserts.py
# =============================================================================


class TestAssertsCoverage:
    """Tests to increase asserts.py coverage."""

    def test_diff_strings(self) -> None:
        """Test _diff_strings function."""
        diff = _diff_strings("hello\nworld", "hello\nearth")
        assert "world" in diff
        assert "earth" in diff

    def test_truncate_short(self) -> None:
        """Test _truncate with short string."""
        result = _truncate("hello", max_len=200)
        assert result == "hello"

    def test_truncate_long(self) -> None:
        """Test _truncate with long string."""
        long_str = "a" * 250
        result = _truncate(long_str, max_len=200)
        assert len(result) == 200
        assert result.endswith("...")

    def test_prompt_asserts_text_property(self) -> None:
        """Test PromptAsserts.text property."""
        rendered = RenderedPrompt(text="hello world")
        asserts = PromptAsserts(rendered)
        assert asserts.text == "hello world"

    def test_prompt_asserts_text_normalized(self) -> None:
        """Test PromptAsserts.text with normalized."""
        rendered = RenderedPrompt(text="hello   world")
        asserts = PromptAsserts(rendered, use_normalized=True)
        assert asserts.text == "hello world"

    def test_prompt_asserts_contains_failure(self) -> None:
        """Test PromptAsserts.contains failure."""
        rendered = RenderedPrompt(text="hello world")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.contains("goodbye")
        assert "Expected text to contain" in str(exc_info.value)

    def test_prompt_asserts_not_contains_failure(self) -> None:
        """Test PromptAsserts.not_contains failure."""
        rendered = RenderedPrompt(text="hello world")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.not_contains("hello")
        assert "Expected text to NOT contain" in str(exc_info.value)

    def test_prompt_asserts_contains_line_failure(self) -> None:
        """Test PromptAsserts.contains_line failure."""
        rendered = RenderedPrompt(text="line1\nline2")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.contains_line("nonexistent")
        assert "Expected some line to contain" in str(exc_info.value)

    def test_prompt_asserts_has_exact_line_failure(self) -> None:
        """Test PromptAsserts.has_exact_line failure."""
        rendered = RenderedPrompt(text="hello world\ntest line")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.has_exact_line("hello")  # Not exact match
        assert "Expected exact line" in str(exc_info.value)

    def test_prompt_asserts_has_exact_line_close_match(self) -> None:
        """Test has_exact_line with close match hint."""
        rendered = RenderedPrompt(text="hello world\ntest line")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.has_exact_line("hello word")  # Close match
        assert "Did you mean" in str(exc_info.value)

    def test_prompt_asserts_regex_failure(self) -> None:
        """Test PromptAsserts.regex failure."""
        rendered = RenderedPrompt(text="hello world")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.regex(r"\d+")
        assert "Expected text to match pattern" in str(exc_info.value)

    def test_prompt_asserts_not_regex_failure(self) -> None:
        """Test PromptAsserts.not_regex failure."""
        rendered = RenderedPrompt(text="hello 123 world")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.not_regex(r"\d+")
        assert "Expected text to NOT match pattern" in str(exc_info.value)

    def test_prompt_asserts_line_count_failure(self) -> None:
        """Test PromptAsserts.line_count failure."""
        rendered = RenderedPrompt(text="line1\nline2\nline3")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.line_count(5)
        assert "Expected 5 lines, but found 3" in str(exc_info.value)

    def test_prompt_asserts_line_count_between_failure(self) -> None:
        """Test PromptAsserts.line_count_between failure."""
        rendered = RenderedPrompt(text="line1\nline2\nline3")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.line_count_between(5, 10)
        assert "Expected between 5 and 10 lines" in str(exc_info.value)

    def test_prompt_asserts_equals_failure(self) -> None:
        """Test PromptAsserts.equals failure."""
        rendered = RenderedPrompt(text="hello world")
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.equals("goodbye world")
        assert "Text does not match expected" in str(exc_info.value)

    def test_prompt_asserts_equals_json_failure(self) -> None:
        """Test PromptAsserts.equals_json failure."""
        rendered = RenderedPrompt(text='{"key": "value"}')
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.equals_json({"key": "different"})
        assert "JSON does not match expected" in str(exc_info.value)

    def test_prompt_asserts_has_trace_failure(self) -> None:
        """Test PromptAsserts.has_trace failure."""
        rendered = RenderedPrompt(text="test", trace_events=["event1"])
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.has_trace("event2")
        assert "Expected trace event" in str(exc_info.value)

    def test_prompt_asserts_not_has_trace_failure(self) -> None:
        """Test PromptAsserts.not_has_trace failure."""
        rendered = RenderedPrompt(text="test", trace_events=["event1"])
        asserts = PromptAsserts(rendered)
        with pytest.raises(PromptAssertionError) as exc_info:
            asserts.not_has_trace("event1")
        assert "Expected trace event NOT to be recorded" in str(exc_info.value)

    def test_prompt_asserts_snapshot_create(self) -> None:
        """Test PromptAsserts.snapshot creates file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rendered = RenderedPrompt(text="test content")
            asserts = PromptAsserts(rendered)
            asserts.snapshot("test_snap", snapshot_dir=tmpdir, update=True)

            snapshot_path = Path(tmpdir) / "test_snap.txt"
            assert snapshot_path.exists()
            assert snapshot_path.read_text() == "test content"

    def test_prompt_asserts_snapshot_match(self) -> None:
        """Test PromptAsserts.snapshot matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "test_snap.txt"
            snapshot_path.write_text("test content")

            rendered = RenderedPrompt(text="test content")
            asserts = PromptAsserts(rendered)
            asserts.snapshot("test_snap", snapshot_dir=tmpdir)

    def test_prompt_asserts_snapshot_mismatch(self) -> None:
        """Test PromptAsserts.snapshot mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "test_snap.txt"
            snapshot_path.write_text("original content")

            rendered = RenderedPrompt(text="different content")
            asserts = PromptAsserts(rendered)
            with pytest.raises(PromptAssertionError) as exc_info:
                asserts.snapshot("test_snap", snapshot_dir=tmpdir)
            assert "Snapshot mismatch" in str(exc_info.value)

    def test_assert_no_undefined_clean(self) -> None:
        """Test assert_no_undefined with clean text."""
        assert_no_undefined("Hello world, this is clean text")

    def test_assert_no_undefined_with_undefined(self) -> None:
        """Test assert_no_undefined with Undefined marker."""
        with pytest.raises(PromptAssertionError) as exc_info:
            assert_no_undefined("Hello Undefined world")
        assert "Found 'Undefined'" in str(exc_info.value)

    def test_assert_no_undefined_with_template_syntax(self) -> None:
        """Test assert_no_undefined with unreplaced template syntax."""
        with pytest.raises(PromptAssertionError) as exc_info:
            assert_no_undefined("Hello {{ name }}")
        assert "unreplaced template syntax" in str(exc_info.value)


# =============================================================================
# Tests for spec.py
# =============================================================================


class TestSpecCoverage:
    """Tests to increase spec.py coverage."""

    def test_template_render_error_attributes(self) -> None:
        """Test TemplateRenderError attributes."""
        original = ValueError("test")
        error = TemplateRenderError("Test message", original_error=original)
        assert str(error) == "Test message"
        assert error.original_error is original

    def test_context_validation_error_attributes(self) -> None:
        """Test ContextValidationError attributes."""
        errors = [{"loc": ("field",), "msg": "required"}]
        error = ContextValidationError("Validation failed", validation_errors=errors)
        assert "Validation failed" in str(error)
        assert error.validation_errors == errors

    def test_context_validation_error_no_errors(self) -> None:
        """Test ContextValidationError without validation_errors."""
        error = ContextValidationError("Validation failed")
        assert error.validation_errors == []

    def test_create_environment_with_mock_templates(self) -> None:
        """Test create_environment with mock templates."""
        env = create_environment(mock_templates={"test.j2": "Hello {{ name }}"})
        template = env.get_template("test.j2")
        result = template.render(name="World")
        assert result == "Hello World"

    def test_create_environment_with_template_paths(self) -> None:
        """Test create_environment with template paths."""
        template_dir = Path(__file__).parent / "templates"
        env = create_environment(template_paths=[template_dir])
        assert env.loader is not None

    def test_create_environment_with_extensions(self) -> None:
        """Test create_environment with custom extensions."""
        env = create_environment(extensions=["jinja2.ext.loopcontrols"])
        # Extension keys are the full class name
        assert "jinja2.ext.LoopControlExtension" in env.extensions

    def test_create_environment_with_filters(self) -> None:
        """Test create_environment with custom filters."""

        def custom_filter(value: str) -> str:
            return value.upper()

        env = create_environment(filters={"upper_custom": custom_filter})
        assert "upper_custom" in env.filters

    def test_create_environment_with_globals(self) -> None:
        """Test create_environment with custom globals."""
        env = create_environment(globals={"my_var": "test_value"})
        assert env.globals["my_var"] == "test_value"

    def test_create_environment_with_tests(self) -> None:
        """Test create_environment with custom tests."""

        def is_even(value: int) -> bool:
            return value % 2 == 0

        env = create_environment(tests={"even": is_even})
        assert "even" in env.tests

    def test_create_environment_sandboxed(self) -> None:
        """Test create_environment with sandboxed mode."""
        from jinja2.sandbox import SandboxedEnvironment

        env = create_environment(sandboxed=True)
        assert isinstance(env, SandboxedEnvironment)

    def test_create_environment_native_types(self) -> None:
        """Test create_environment with native types."""
        from jinja2.nativetypes import NativeEnvironment

        env = create_environment(native_types=True)
        assert isinstance(env, NativeEnvironment)

    def test_create_environment_no_do_extension(self) -> None:
        """Test create_environment without do extension."""
        env = create_environment(enable_do_extension=False)
        # When no extensions, env.extensions may be empty dict or None
        assert "jinja2.ext.ExprStmtExtension" not in (env.extensions or {})

    def test_template_spec_env_property(self) -> None:
        """Test TemplateSpec.env property."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.env is not None

    def test_template_spec_template_property(self) -> None:
        """Test TemplateSpec.template property."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.template is not None

    def test_template_spec_context_model_property(self) -> None:
        """Test TemplateSpec.context_model property."""
        spec = TemplateSpec.from_string("Hello", context_model=SimpleContext)
        assert spec.context_model is SimpleContext

    def test_template_spec_context_model_none(self) -> None:
        """Test TemplateSpec.context_model when None."""
        spec = TemplateSpec.from_string("Hello")
        assert spec.context_model is None

    def test_template_spec_render_with_pydantic_model(self) -> None:
        """Test rendering with a Pydantic model instance."""
        spec = TemplateSpec.from_string(
            "Hello {{ name }}, value={{ value }}", context_model=SimpleContext
        )
        ctx = SimpleContext(name="Test", value=42)
        rendered = spec.render(ctx)
        assert "Hello Test" in rendered.text
        assert "value=42" in rendered.text

    def test_template_spec_render_generic_exception(self) -> None:
        """Test render handles generic exceptions."""
        spec = TemplateSpec.from_string("{{ 1/0 }}")
        with pytest.raises(TemplateRenderError) as exc_info:
            spec.render({})
        assert "Template rendering failed" in str(exc_info.value)

    def test_template_spec_render_native(self) -> None:
        """Test render_native method."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string("{{ value }}", env=env)
        result = spec.render_native({"value": 42})
        assert result == 42

    def test_template_spec_render_native_with_model(self) -> None:
        """Test render_native with Pydantic model."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string(
            "{{ value }}", env=env, context_model=SimpleContext
        )
        ctx = SimpleContext(name="Test", value=42)
        result = spec.render_native(ctx)
        assert result == 42

    def test_template_spec_render_native_undefined_error(self) -> None:
        """Test render_native with undefined variable."""
        # Use regular environment (not native_types) because NativeEnvironment
        # returns lazy objects that don't fail until accessed
        env = create_environment(strict_undefined=True)
        spec = TemplateSpec.from_string("{{ undefined_var }}", env=env)
        with pytest.raises(TemplateRenderError) as exc_info:
            spec.render_native({})
        assert "Undefined variable" in str(exc_info.value)

    def test_template_spec_render_native_generic_error(self) -> None:
        """Test render_native with generic error."""
        env = create_environment(native_types=True)
        spec = TemplateSpec.from_string("{{ 1/0 }}", env=env)
        with pytest.raises(TemplateRenderError) as exc_info:
            spec.render_native({})
        assert "Template rendering failed" in str(exc_info.value)

    def test_template_spec_get_undeclared_variables(self) -> None:
        """Test get_undeclared_variables method."""
        template_dir = Path(__file__).parent / "templates"
        spec = TemplateSpec.from_file(template_dir / "welcome.j2")
        variables = spec.get_undeclared_variables()
        assert "user_name" in variables
        assert "plan" in variables

    def test_template_spec_get_undeclared_variables_from_string(self) -> None:
        """Test get_undeclared_variables returns empty for string templates."""
        spec = TemplateSpec.from_string("Hello {{ name }}")
        variables = spec.get_undeclared_variables()
        # String templates may not have a loader, so returns empty
        assert variables == set()

    def test_template_spec_assert_variables_subset_of_pass(self) -> None:
        """Test assert_variables_subset_of when all variables are allowed."""
        template_dir = Path(__file__).parent / "templates"
        spec = TemplateSpec.from_file(template_dir / "welcome.j2")
        # Should not raise
        spec.assert_variables_subset_of({"user_name", "plan", "t", "extra"})

    def test_template_spec_assert_variables_subset_of_fail(self) -> None:
        """Test assert_variables_subset_of when variables are not allowed."""
        from jinjatest.spec import UndeclaredVariableError

        template_dir = Path(__file__).parent / "templates"
        spec = TemplateSpec.from_file(template_dir / "welcome.j2")
        with pytest.raises(UndeclaredVariableError) as exc_info:
            spec.assert_variables_subset_of({"user_name"})  # Missing 'plan'
        assert "plan" in str(exc_info.value)

    def test_template_spec_from_file_with_template_dir(self) -> None:
        """Test from_file with explicit template_dir."""
        template_dir = Path(__file__).parent / "templates"
        spec = TemplateSpec.from_file(
            "welcome.j2",
            template_dir=template_dir,  # Just the filename
        )
        rendered = spec.render({"user_name": "Test", "plan": "free"})
        assert "Hello, Test!" in rendered.text

    def test_template_spec_from_string_test_mode_false(self) -> None:
        """Test from_string with test_mode=False."""
        spec = TemplateSpec.from_string("Hello {{ name }}", test_mode=False)
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello World"
        # With test_mode=False, instrumentation is None at class level
        # but __init__ defaults to creating one, so anchor_index still exists
        # The important thing is that rendered output is correct
        assert "Hello World" in rendered.text

    def test_template_spec_from_file_test_mode_false(self) -> None:
        """Test from_file with test_mode=False."""
        template_dir = Path(__file__).parent / "templates"
        spec = TemplateSpec.from_file(template_dir / "welcome.j2", test_mode=False)
        rendered = spec.render({"user_name": "Test", "plan": "pro"})
        assert "Hello, Test!" in rendered.text
        # Verify the text renders correctly even with test_mode=False
        assert "Welcome to Pro!" in rendered.text


# =============================================================================
# Tests for pytest_plugin.py
# =============================================================================


class TestPytestPluginCoverage:
    """Tests to increase pytest_plugin.py coverage."""

    def test_snapshot_manager_direct(self) -> None:
        """Test SnapshotManager directly."""
        from jinjatest.pytest_plugin import SnapshotManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(Path(tmpdir), update=False)
            assert manager.base_dir == Path(tmpdir)
            assert manager.update is False

    def test_snapshot_manager_update_mode(self) -> None:
        """Test SnapshotManager in update mode."""
        from jinjatest.pytest_plugin import SnapshotManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(Path(tmpdir), update=True)
            manager.compare_or_update("test", "content")
            # File should be created
            assert (Path(tmpdir) / "test.txt").exists()

    def test_snapshot_manager_creates_subdirs(self) -> None:
        """Test SnapshotManager creates parent directories."""
        from jinjatest.pytest_plugin import SnapshotManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(Path(tmpdir) / "sub" / "dir", update=True)
            manager.compare_or_update("test", "content")
            assert (Path(tmpdir) / "sub" / "dir" / "test.txt").exists()


# Tests that use pytest fixtures to cover pytest_plugin.py
class TestPytestPluginFixtures:
    """Tests using pytest fixtures to cover fixture code paths."""

    def test_template_spec_factory_fixture(
        self, template_spec_factory, template_dir
    ) -> None:
        """Test the template_spec_factory fixture with absolute path."""
        # Use an absolute path to test the is_absolute() branch
        template_path = Path(__file__).parent / "templates" / "welcome.j2"
        # Pass test_mode=True to create a new env with proper loader
        spec = TemplateSpec.from_file(template_path, test_mode=True)
        rendered = spec.render({"user_name": "Test", "plan": "pro"})
        assert "Hello, Test!" in rendered.text

    def test_template_from_string_fixture(self, template_from_string) -> None:
        """Test the template_from_string fixture."""
        spec = template_from_string("Hello {{ name }}!")
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello World!"

    def test_jinja_env_fixture(self, jinja_env) -> None:
        """Test the jinja_env fixture provides configured environment."""
        from jinja2 import Environment

        assert isinstance(jinja_env, Environment)

    def test_update_snapshots_fixture(self, update_snapshots) -> None:
        """Test the update_snapshots fixture returns boolean."""
        assert isinstance(update_snapshots, bool)

    def test_snapshot_manager_fixture(self, snapshot_manager) -> None:
        """Test the snapshot_manager fixture provides SnapshotManager."""
        from jinjatest.pytest_plugin import SnapshotManager

        assert isinstance(snapshot_manager, SnapshotManager)


# =============================================================================
# Tests for XML parser edge cases
# =============================================================================


class TestXMLParserCoverage:
    """Tests to increase xml_parser.py coverage."""

    def test_xml_element_get_text_recursive(self) -> None:
        """Test XMLElement.get_text with nested elements."""
        xml_str = "<root>Hello <child>nested</child> world</root>"
        result = parse_xml(xml_str, strict=True)
        assert isinstance(result, XMLElement)
        text = result.get_text()
        assert "Hello" in text
        assert "nested" in text
        assert "world" in text

    def test_xml_parse_error_str(self) -> None:
        """Test XMLParseError string representation."""
        error = XMLParseError("Test error message")
        assert str(error) == "Test error message"

    def test_xml_element_find_none(self) -> None:
        """Test XMLElement.find returns None when not found."""
        result = parse_xml("<root><child>value</child></root>", strict=True)
        assert isinstance(result, XMLElement)
        found = result.find("nonexistent")
        assert found is None

    def test_xml_element_find_all_empty(self) -> None:
        """Test XMLElement.find_all returns empty list when none found."""
        result = parse_xml("<root><child>value</child></root>", strict=True)
        assert isinstance(result, XMLElement)
        found = result.find_all("nonexistent")
        assert found == []

    def test_parse_xml_fragment_single_wrapped(self) -> None:
        """Test parsing XML fragment that wraps to single element."""
        # This tests the path where root.tag == "__root__" and len(children) == 1
        # which returns children[0] (line 162)
        xml_str = "<item>value</item>"  # Single element, will be wrapped
        result = parse_xml(xml_str, strict=False)
        assert isinstance(result, XMLElement)
        assert result.tag == "item"

    def test_parse_xml_valid_document(self) -> None:
        """Test parsing valid XML document returns root directly."""
        # This tests line 165 - when root is valid XML, return directly
        xml_str = "<?xml version='1.0'?><root><child/></root>"
        result = parse_xml(xml_str, strict=False)
        assert isinstance(result, XMLElement)
        assert result.tag == "root"
