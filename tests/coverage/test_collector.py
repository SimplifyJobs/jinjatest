"""Tests for coverage collector."""

from jinjatest.coverage.collector import (
    CoverageCollector,
    CoverageSummary,
    get_coverage_collector,
    reset_coverage_collector,
    set_coverage_collector,
)


class TestCoverageSummary:
    """Tests for CoverageSummary dataclass."""

    def test_empty_summary(self) -> None:
        """Test empty summary."""
        summary = CoverageSummary(templates=[])
        assert summary.total_branches == 0
        assert summary.covered_branches == 0
        assert summary.coverage_percent == 100.0
        assert summary.template_count == 0

    def test_summary_with_templates(self) -> None:
        """Test summary with template stats."""
        from jinjatest.coverage.tracker import TemplateCoverageStats

        stats1 = TemplateCoverageStats(
            template_path="test1.j2",
            total_branches=4,
            covered_branches=2,
            branch_details=[],
        )
        stats2 = TemplateCoverageStats(
            template_path="test2.j2",
            total_branches=6,
            covered_branches=6,
            branch_details=[],
        )

        summary = CoverageSummary(templates=[stats1, stats2])
        assert summary.total_branches == 10
        assert summary.covered_branches == 8
        assert summary.coverage_percent == 80.0
        assert summary.template_count == 2

    def test_get_template_stats(self) -> None:
        """Test getting stats for specific template."""
        from jinjatest.coverage.tracker import TemplateCoverageStats

        stats1 = TemplateCoverageStats(
            template_path="test1.j2",
            total_branches=4,
            covered_branches=2,
            branch_details=[],
        )

        summary = CoverageSummary(templates=[stats1])
        result = summary.get_template_stats("test1.j2")
        assert result is not None
        assert result.template_path == "test1.j2"

    def test_get_template_stats_not_found(self) -> None:
        """Test getting stats for non-existent template."""
        summary = CoverageSummary(templates=[])
        assert summary.get_template_stats("nonexistent.j2") is None


class TestCoverageCollector:
    """Tests for CoverageCollector class."""

    def test_initial_state(self) -> None:
        """Test collector initial state."""
        collector = CoverageCollector()
        assert collector.enabled is False

    def test_enable_disable(self) -> None:
        """Test enabling and disabling collector."""
        collector = CoverageCollector()

        collector.enable()
        assert collector.enabled is True

        collector.disable()
        assert collector.enabled is False

    def test_register_template_when_disabled(self) -> None:
        """Test register_template returns source unchanged when disabled."""
        collector = CoverageCollector()
        source = "{% if x %}y{% endif %}"

        result = collector.register_template("test.j2", source)
        assert result == source

    def test_register_template_when_enabled(self) -> None:
        """Test register_template instruments source when enabled."""
        collector = CoverageCollector()
        collector.enable()

        source = "{% if x %}y{% endif %}"
        result = collector.register_template("test.j2", source)

        assert "jt.trace" in result

    def test_register_template_idempotent(self) -> None:
        """Test registering same template twice returns same source."""
        collector = CoverageCollector()
        collector.enable()

        source = "{% if x %}y{% endif %}"
        result1 = collector.register_template("test.j2", source)
        result2 = collector.register_template("test.j2", source)

        assert result1 == result2

    def test_record_render_when_disabled(self) -> None:
        """Test record_render does nothing when disabled."""
        collector = CoverageCollector()
        collector.record_render("test.j2", ["if_1_true"])

    def test_record_render_when_enabled(self) -> None:
        """Test record_render records hits when enabled."""
        collector = CoverageCollector()
        collector.enable()

        source = "{% if x %}y{% endif %}"
        collector.register_template("test.j2", source)
        collector.record_render("test.j2", ["if_1_true"])

        tracker = collector.get_tracker("test.j2")
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1

    def test_get_tracker(self) -> None:
        """Test getting tracker for template."""
        collector = CoverageCollector()
        collector.enable()

        collector.register_template("test.j2", "{% if x %}y{% endif %}")
        tracker = collector.get_tracker("test.j2")

        assert tracker is not None
        assert tracker.template_path == "test.j2"

    def test_get_tracker_not_found(self) -> None:
        """Test getting tracker for unregistered template."""
        collector = CoverageCollector()
        assert collector.get_tracker("nonexistent.j2") is None

    def test_get_summary(self) -> None:
        """Test getting summary."""
        collector = CoverageCollector()
        collector.enable()

        collector.register_template("test1.j2", "{% if a %}b{% endif %}")
        collector.register_template("test2.j2", "{% if c %}d{% endif %}")
        collector.record_render("test1.j2", ["if_1_true"])

        summary = collector.get_summary()
        assert summary.template_count == 2
        assert summary.total_branches == 4
        assert summary.covered_branches == 1

    def test_reset(self) -> None:
        """Test resetting collector."""
        collector = CoverageCollector()
        collector.enable()

        collector.register_template("test.j2", "{% if x %}y{% endif %}")
        collector.record_render("test.j2", ["if_1_true"])

        collector.reset()

        summary = collector.get_summary()
        assert summary.template_count == 0

    def test_get_all_trackers(self) -> None:
        """Test getting all trackers."""
        collector = CoverageCollector()
        collector.enable()

        collector.register_template("test1.j2", "{% if a %}b{% endif %}")
        collector.register_template("test2.j2", "{% if c %}d{% endif %}")

        trackers = collector.get_all_trackers()
        assert len(trackers) == 2
        assert "test1.j2" in trackers
        assert "test2.j2" in trackers


class TestGlobalCollector:
    """Tests for global collector functions."""

    def test_get_coverage_collector(self) -> None:
        """Test getting global collector."""
        set_coverage_collector(None)

        collector = get_coverage_collector()
        assert collector is not None
        assert isinstance(collector, CoverageCollector)

    def test_get_coverage_collector_singleton(self) -> None:
        """Test global collector is singleton."""
        set_coverage_collector(None)

        collector1 = get_coverage_collector()
        collector2 = get_coverage_collector()
        assert collector1 is collector2

    def test_set_coverage_collector(self) -> None:
        """Test setting global collector."""
        custom = CoverageCollector()
        set_coverage_collector(custom)

        assert get_coverage_collector() is custom
        set_coverage_collector(None)

    def test_reset_coverage_collector(self) -> None:
        """Test resetting global collector."""
        set_coverage_collector(None)
        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        reset_coverage_collector()

        summary = collector.get_summary()
        assert summary.template_count == 0
        assert collector.enabled is False
