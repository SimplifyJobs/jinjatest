"""Tests for coverage recording on render_native and macro render paths."""

from pathlib import Path

from jinjatest import TemplateSpec
from jinjatest.coverage.collector import (
    get_coverage_collector,
    reset_coverage_collector,
)


class TestRenderNativeCoverage:
    """Tests for coverage recording via TemplateSpec.render_native."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_render_native_records_if_branch(self, tmp_path: Path) -> None:
        """Test render_native records a hit for the taken if branch."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "native_branch.j2"
        template_file.write_text("{% if flag %}1{% else %}0{% endif %}")

        spec = TemplateSpec.from_file(template_file, native_types=True)
        cov_path = str(template_file.resolve())

        result = spec.render_native({"flag": True})
        assert result == 1

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1

    def test_render_native_records_else_branch(self, tmp_path: Path) -> None:
        """Test render_native records a hit for the else branch."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "native_else.j2"
        template_file.write_text("{% if flag %}1{% else %}0{% endif %}")

        spec = TemplateSpec.from_file(template_file, native_types=True)
        cov_path = str(template_file.resolve())

        result = spec.render_native({"flag": False})
        assert result == 0

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("if_1_false") == 1

    def test_render_native_accumulates_hits(self, tmp_path: Path) -> None:
        """Test repeated render_native calls accumulate coverage hits."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "native_multi.j2"
        template_file.write_text("{% if flag %}1{% else %}0{% endif %}")

        spec = TemplateSpec.from_file(template_file, native_types=True)
        cov_path = str(template_file.resolve())

        spec.render_native({"flag": True})
        spec.render_native({"flag": False})

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1
        assert tracker.get_hit_count("if_1_false") == 1


class TestMacroCoverage:
    """Tests for coverage recording via TemplateSpec.macro."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_macro_call_records_coverage(self, tmp_path: Path) -> None:
        """Test invoking a macro records coverage for its branches."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "macros.j2"
        template_file.write_text(
            "{% macro m(x) %}{% if x %}yes{% else %}no{% endif %}{% endmacro %}"
        )

        spec = TemplateSpec.from_file(template_file)
        cov_path = str(template_file.resolve())

        result = spec.macro("m")(True)
        assert "yes" in str(result)

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("macro_m") == 1
        assert tracker.get_hit_count("if_1_true") == 1
        assert tracker.get_hit_count("if_1_false") == 0

    def test_macro_records_each_invocation(self, tmp_path: Path) -> None:
        """Test each macro invocation records its own branch hits."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "macros_both.j2"
        template_file.write_text(
            "{% macro m(x) %}{% if x %}yes{% else %}no{% endif %}{% endmacro %}"
        )

        spec = TemplateSpec.from_file(template_file)
        cov_path = str(template_file.resolve())

        spec.macro("m")(True)
        spec.macro("m")(False)

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1
        assert tracker.get_hit_count("if_1_false") == 1

    def test_macro_repeated_calls_do_not_double_count(self, tmp_path: Path) -> None:
        """Test stale trace events are not re-recorded on repeat calls."""
        collector = get_coverage_collector()
        collector.enable()

        template_file = tmp_path / "macros_repeat.j2"
        template_file.write_text(
            "{% macro m(x) %}{% if x %}yes{% else %}no{% endif %}{% endmacro %}"
        )

        spec = TemplateSpec.from_file(template_file)
        cov_path = str(template_file.resolve())

        macro_fn = spec.macro("m")
        macro_fn(True)
        macro_fn(True)

        tracker = collector.get_tracker(cov_path)
        assert tracker is not None
        assert tracker.get_hit_count("macro_m") == 2
        assert tracker.get_hit_count("if_1_true") == 2
