"""Tests for instrumentation (anchors and traces)."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from jinjatest import PromptAsserts, TemplateSpec


class AnchoredContext(BaseModel):
    user_name: str
    request: str
    context_items: list[str]


TEMPLATE_DIR = Path(__file__).parent / "templates"


class TestAnchors:
    """Test anchor functionality."""

    def test_section_access(self) -> None:
        """Test accessing sections by anchor name."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Help me code",
                "context_items": ["item1", "item2"],
            }
        )

        # Access specific sections
        system_section = rendered.section("system")
        assert "Be helpful" in system_section.text
        assert "Be concise" in system_section.text

        user_section = rendered.section("user")
        assert "Ada" in user_section.text
        assert "Help me code" in user_section.text

        context_section = rendered.section("context")
        assert "item1" in context_section.text
        assert "item2" in context_section.text

    def test_section_isolation(self) -> None:
        """Test that sections don't leak into each other."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],
            }
        )

        system_section = rendered.section("system")
        assert "Ada" not in system_section.text  # User name shouldn't be in system

        user_section = rendered.section("user")
        assert (
            "Be helpful" not in user_section.text
        )  # System rules shouldn't be in user

    def test_section_assertions(self) -> None:
        """Test assertions on sections."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Help",
                "context_items": ["doc1"],
            }
        )

        assert rendered.section("user").contains("Ada")
        assert rendered.section("system").not_contains("Ada")
        assert rendered.section("context").contains("doc1")

    def test_missing_section_error(self) -> None:
        """Test that accessing missing section raises KeyError."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],
            }
        )

        with pytest.raises(KeyError) as exc_info:
            rendered.section("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "Available anchors" in str(exc_info.value)

    def test_list_sections(self) -> None:
        """Test listing all sections."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],
            }
        )

        sections = rendered.sections()
        assert set(sections.keys()) == {"system", "user", "context"}

    def test_clean_text_removes_markers(self) -> None:
        """Test that clean_text removes anchor markers."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],
            }
        )

        # Raw text has markers, clean_text doesn't
        assert "ANCHOR:" not in rendered.clean_text
        assert "\x1e" not in rendered.clean_text


class TestTraces:
    """Test trace functionality."""

    def test_trace_recorded(self) -> None:
        """Test that trace events are recorded."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],  # Empty triggers no_context trace
            }
        )

        assert rendered.has_trace("no_context")
        assert rendered.trace_count("no_context") == 1

    def test_trace_not_recorded(self) -> None:
        """Test that trace events are not recorded when branch not taken."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": ["item1"],  # Non-empty, so no_context not triggered
            }
        )

        assert not rendered.has_trace("no_context")

    def test_trace_assertion(self) -> None:
        """Test trace assertions with PromptAsserts."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": [],
            }
        )

        PromptAsserts(rendered).has_trace("no_context")

    def test_trace_not_has_assertion(self) -> None:
        """Test not_has_trace assertion."""
        spec = TemplateSpec.from_file(
            TEMPLATE_DIR / "anchored.j2",
            context_model=AnchoredContext,
        )
        rendered = spec.render(
            {
                "user_name": "Ada",
                "request": "Test",
                "context_items": ["item1"],
            }
        )

        PromptAsserts(rendered).not_has_trace("no_context")


class TestInlineInstrumentation:
    """Test instrumentation with inline templates."""

    def test_inline_anchor(self) -> None:
        """Test anchors in inline templates."""
        spec = TemplateSpec.from_string("""{{ jt.anchor("header") }}
# Welcome
{{ jt.anchor("body") }}
Hello, {{ name }}!""")

        rendered = spec.render({"name": "Ada"})

        assert "Welcome" in rendered.section("header").text
        assert "Ada" in rendered.section("body").text

    def test_inline_trace(self) -> None:
        """Test traces in inline templates."""
        spec = TemplateSpec.from_string("""{% if show_extra %}
Extra content
{{ jt.trace("showed_extra") }}
{% endif %}
Main content""")

        rendered_with = spec.render({"show_extra": True})
        assert rendered_with.has_trace("showed_extra")

        rendered_without = spec.render({"show_extra": False})
        assert not rendered_without.has_trace("showed_extra")


class TestAnchorIndexDirect:
    """Direct tests for AnchorIndex class."""

    def test_anchor_index_from_text_no_anchors(self) -> None:
        """Test AnchorIndex.from_text with no anchors."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex.from_text("Plain text without anchors")
        assert index.clean_text == "Plain text without anchors"
        assert index.anchors == {}

    def test_anchor_index_get_section_not_found(self) -> None:
        """Test AnchorIndex.get_section returns None for non-existent."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex()
        assert index.get_section("nonexistent") is None

    def test_anchor_index_has_anchor(self) -> None:
        """Test AnchorIndex.has_anchor method."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex(anchors={"test": (0, 10)}, clean_text="0123456789")
        assert index.has_anchor("test") is True
        assert index.has_anchor("nonexistent") is False

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

    def test_anchor_index_get_section_valid(self) -> None:
        """Test get_section returns correct content."""
        from jinjatest.instrumentation import AnchorIndex

        index = AnchorIndex(
            anchors={"test": (0, 5)},
            clean_text="Hello World",
        )
        assert index.get_section("test") == "Hello"


class TestTraceRecorderDirect:
    """Direct tests for TraceRecorder class."""

    def test_trace_recorder_clear(self) -> None:
        """Test TraceRecorder.clear method."""
        from jinjatest.instrumentation import TraceRecorder

        recorder = TraceRecorder()
        recorder.record("event1")
        recorder.record("event2")
        assert len(recorder.events) == 2

        recorder.clear()
        assert len(recorder.events) == 0

    def test_trace_recorder_multiple_events(self) -> None:
        """Test TraceRecorder with multiple events."""
        from jinjatest.instrumentation import TraceRecorder

        recorder = TraceRecorder()
        recorder.record("event1")
        recorder.record("event2")
        recorder.record("event1")

        assert len(recorder.events) == 3
        assert recorder.events.count("event1") == 2


class TestInstrumentationDisabled:
    """Test instrumentation when disabled."""

    def test_test_instrumentation_disabled(self) -> None:
        """Test TestInstrumentation when disabled."""
        from jinjatest.instrumentation import TestInstrumentation

        inst = TestInstrumentation()
        inst._enabled = False

        assert inst.anchor("test") == ""
        assert inst.trace("event") == ""

    def test_test_instrumentation_trace_events_copy(self) -> None:
        """Test that trace_events returns a copy."""
        from jinjatest.instrumentation import TestInstrumentation

        inst = TestInstrumentation()
        inst.trace("event1")

        events = inst.trace_events
        events.append("modified")

        assert "modified" not in inst.trace_events

    def test_production_instrumentation_trace_events(self) -> None:
        """Test ProductionInstrumentation.trace_events."""
        from jinjatest.instrumentation import ProductionInstrumentation

        inst = ProductionInstrumentation()
        assert inst.trace_events == []

    def test_production_instrumentation_clear(self) -> None:
        """Test ProductionInstrumentation.clear (no-op)."""
        from jinjatest.instrumentation import ProductionInstrumentation

        inst = ProductionInstrumentation()
        inst.clear()  # Should not raise
