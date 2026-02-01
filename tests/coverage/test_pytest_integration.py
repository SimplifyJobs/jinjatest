"""Tests for pytest plugin integration."""

from jinjatest import TemplateSpec
from jinjatest.coverage.collector import (
    get_coverage_collector,
    reset_coverage_collector,
)


class TestPytestIntegration:
    """Tests for pytest plugin integration with coverage."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_coverage_disabled_by_default(self) -> None:
        """Test that coverage is disabled by default."""
        collector = get_coverage_collector()
        assert collector.enabled is False

    def test_template_spec_without_coverage(self) -> None:
        """Test TemplateSpec works normally without coverage."""
        spec = TemplateSpec.from_string("""{% if show %}
Content
{% else %}
Hidden
{% endif %}""")

        rendered = spec.render({"show": True})
        assert "Content" in rendered.text

    def test_template_spec_with_coverage_enabled(self) -> None:
        """Test TemplateSpec integrates with coverage when enabled."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if show %}
Content
{% else %}
Hidden
{% endif %}""",
            template_path="test_inline.j2",
        )

        rendered = spec.render({"show": True})
        assert "Content" in rendered.text

        # Check coverage was recorded
        summary = collector.get_summary()
        assert summary.template_count == 1
        assert summary.covered_branches >= 1

    def test_coverage_tracks_multiple_renders(self) -> None:
        """Test coverage tracks multiple renders of same template."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if show %}
Content
{% else %}
Hidden
{% endif %}""",
            template_path="multi_render.j2",
        )

        # Render with show=True
        spec.render({"show": True})

        # Render with show=False
        spec.render({"show": False})

        summary = collector.get_summary()
        stats = summary.get_template_stats("multi_render.j2")
        assert stats is not None
        # Both branches should now be covered
        assert stats.covered_branches == 2

    def test_coverage_tracks_for_loops(self) -> None:
        """Test coverage tracks for loop branches."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% for item in items %}
- {{ item }}
{% else %}
No items
{% endfor %}""",
            template_path="for_loop.j2",
        )

        # Render with items
        spec.render({"items": ["a", "b", "c"]})

        summary = collector.get_summary()
        assert summary.covered_branches >= 1

    def test_coverage_with_nested_conditions(self) -> None:
        """Test coverage tracks nested conditions."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if level1 %}
{% if level2 %}
Deep content
{% endif %}
{% endif %}""",
            template_path="nested.j2",
        )

        spec.render({"level1": True, "level2": True})

        summary = collector.get_summary()
        assert summary.covered_branches >= 2

    def test_coverage_coexists_with_traces(self) -> None:
        """Test coverage works alongside manual traces."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if show %}
{{ jt.trace("manual_trace") }}
Content
{% endif %}""",
            template_path="with_traces.j2",
        )

        rendered = spec.render({"show": True})

        # Manual trace should still work
        assert rendered.has_trace("manual_trace")

        # Coverage should also be tracked
        summary = collector.get_summary()
        assert summary.covered_branches >= 1

    def test_coverage_coexists_with_anchors(self) -> None:
        """Test coverage works alongside anchors."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{{ jt.anchor("header") }}
{% if show %}
Header content
{% endif %}
{{ jt.anchor("footer") }}
Footer""",
            template_path="with_anchors.j2",
        )

        rendered = spec.render({"show": True})

        # Anchors should still work
        assert rendered.has_section("header")
        assert rendered.has_section("footer")

        # Coverage should also be tracked
        summary = collector.get_summary()
        assert summary.covered_branches >= 1


class TestImplicitFalseBranchIntegration:
    """Tests for implicit false branch coverage integration."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_implicit_false_trace_fires_when_condition_false(self) -> None:
        """Test that implicit false trace fires when if condition is false."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if show %}
Shown
{% endif %}""",
            template_path="implicit_false.j2",
        )

        # Render with show=False - should trigger implicit false branch
        rendered = spec.render({"show": False})

        # The false branch trace should have fired
        assert rendered.has_trace("if_1_false")

        # Coverage should show the false branch was hit
        summary = collector.get_summary()
        stats = summary.get_template_stats("implicit_false.j2")
        assert stats is not None
        covered_ids = [bc.branch.branch_id for bc in stats.covered_branch_list]
        assert "if_1_false" in covered_ids

    def test_implicit_false_both_branches_covered(self) -> None:
        """Test that both true and false branches can be covered."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if show %}
Shown
{% endif %}""",
            template_path="both_branches.j2",
        )

        # Render with show=True
        result_true = spec.render({"show": True})
        assert result_true.has_trace("if_1_true")

        # Render with show=False
        result_false = spec.render({"show": False})
        assert result_false.has_trace("if_1_false")

        # Both branches should be covered
        summary = collector.get_summary()
        stats = summary.get_template_stats("both_branches.j2")
        assert stats is not None
        assert stats.covered_branches == 2
        assert stats.coverage_percent == 100.0

    def test_nested_implicit_false(self) -> None:
        """Test nested bare ifs both track implicit false."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if outer %}
{% if inner %}
Content
{% endif %}
{% endif %}""",
            template_path="nested_bare.j2",
        )

        # All branches false
        rendered = spec.render({"outer": False, "inner": False})
        assert rendered.has_trace("if_1_false")
        # Inner won't fire because outer is false

        # Now test with outer true, inner false
        rendered2 = spec.render({"outer": True, "inner": False})
        assert rendered2.has_trace("if_1_true")
        assert rendered2.has_trace("if_2_false")

    def test_elif_implicit_false(self) -> None:
        """Test elif chain without else tracks implicit false."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% if level == 1 %}
One
{% elif level == 2 %}
Two
{% endif %}""",
            template_path="elif_bare.j2",
        )

        # Neither condition true - should hit elif false
        rendered = spec.render({"level": 3})
        # When if is false, the elif is evaluated, and if that's also false,
        # the implicit false branch fires
        assert rendered.has_trace("elif_3_false")

    def test_for_implicit_else_fires_when_empty(self) -> None:
        """Test that implicit else trace fires when for loop is empty."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{% for item in items %}
{{ item }}
{% endfor %}""",
            template_path="for_bare.j2",
        )

        # Render with empty items - should trigger implicit else
        rendered = spec.render({"items": []})
        assert rendered.has_trace("for_1_else")

        # Render with items - should trigger body
        rendered2 = spec.render({"items": ["a", "b"]})
        assert rendered2.has_trace("for_1_body")

        # Both branches should be covered
        summary = collector.get_summary()
        stats = summary.get_template_stats("for_bare.j2")
        assert stats is not None
        assert stats.covered_branches == 2


class TestCoverageWithCommentMarkers:
    """Tests for coverage with comment-based markers."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_coverage_with_jt_markers(self) -> None:
        """Test coverage works with {#jt:...#} markers."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            """{#jt:anchor:start#}
{% if show %}
{#jt:trace:showed_content#}
Content
{% endif %}
{#jt:anchor:end#}""",
            template_path="with_markers.j2",
        )

        rendered = spec.render({"show": True})

        # Markers should work
        assert rendered.has_trace("showed_content")
        assert rendered.has_section("start")

        # Coverage should also be tracked
        summary = collector.get_summary()
        assert summary.covered_branches >= 1
