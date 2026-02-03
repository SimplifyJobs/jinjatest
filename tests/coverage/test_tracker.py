"""Tests for template coverage tracker."""

from jinjatest.coverage.tracker import (
    BranchCoverage,
    TemplateCoverage,
    TemplateCoverageStats,
)


class TestBranchCoverage:
    """Tests for BranchCoverage dataclass."""

    def test_was_hit_false(self) -> None:
        """Test was_hit returns False when hit_count is 0."""
        from jinjatest.coverage.discovery import BranchInfo

        branch = BranchInfo("if_1_true", "if_true", 1, "desc")
        bc = BranchCoverage(branch=branch, hit_count=0)
        assert bc.was_hit is False

    def test_was_hit_true(self) -> None:
        """Test was_hit returns True when hit_count > 0."""
        from jinjatest.coverage.discovery import BranchInfo

        branch = BranchInfo("if_1_true", "if_true", 1, "desc")
        bc = BranchCoverage(branch=branch, hit_count=1)
        assert bc.was_hit is True


class TestTemplateCoverageStats:
    """Tests for TemplateCoverageStats dataclass."""

    def test_empty_stats(self) -> None:
        """Test stats with no branches."""
        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=0,
            covered_branches=0,
            branch_details=[],
        )
        assert stats.coverage_percent == 100.0

    def test_full_coverage(self) -> None:
        """Test stats with full coverage."""
        from jinjatest.coverage.discovery import BranchInfo

        branch = BranchInfo("if_1_true", "if_true", 1, "desc")
        bc = BranchCoverage(branch=branch, hit_count=1)

        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=1,
            covered_branches=1,
            branch_details=[bc],
        )
        assert stats.coverage_percent == 100.0

    def test_partial_coverage(self) -> None:
        """Test stats with partial coverage."""
        from jinjatest.coverage.discovery import BranchInfo

        branch1 = BranchInfo("if_1_true", "if_true", 1, "desc")
        branch2 = BranchInfo("if_1_false", "if_false", 1, "desc")
        bc1 = BranchCoverage(branch=branch1, hit_count=1)
        bc2 = BranchCoverage(branch=branch2, hit_count=0)

        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=2,
            covered_branches=1,
            branch_details=[bc1, bc2],
        )
        assert stats.coverage_percent == 50.0

    def test_uncovered_branches(self) -> None:
        """Test getting uncovered branches."""
        from jinjatest.coverage.discovery import BranchInfo

        branch1 = BranchInfo("if_1_true", "if_true", 1, "desc")
        branch2 = BranchInfo("if_1_false", "if_false", 1, "desc")
        bc1 = BranchCoverage(branch=branch1, hit_count=1)
        bc2 = BranchCoverage(branch=branch2, hit_count=0)

        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=2,
            covered_branches=1,
            branch_details=[bc1, bc2],
        )

        uncovered = stats.uncovered_branches
        assert len(uncovered) == 1
        assert uncovered[0].branch.branch_id == "if_1_false"

    def test_covered_branch_list(self) -> None:
        """Test getting covered branches."""
        from jinjatest.coverage.discovery import BranchInfo

        branch1 = BranchInfo("if_1_true", "if_true", 1, "desc")
        branch2 = BranchInfo("if_1_false", "if_false", 1, "desc")
        bc1 = BranchCoverage(branch=branch1, hit_count=1)
        bc2 = BranchCoverage(branch=branch2, hit_count=0)

        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=2,
            covered_branches=1,
            branch_details=[bc1, bc2],
        )

        covered = stats.covered_branch_list
        assert len(covered) == 1
        assert covered[0].branch.branch_id == "if_1_true"


class TestTemplateCoverage:
    """Tests for TemplateCoverage class."""

    def test_basic_tracking(self) -> None:
        """Test basic coverage tracking."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source, "test.j2")

        assert tracker.template_path == "test.j2"
        assert tracker.source == source
        assert "jt.trace" in tracker.instrumented_source

    def test_record_hits(self) -> None:
        """Test recording trace hits."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        # Initially no hits
        assert tracker.get_hit_count("if_1_true") == 0

        # Record a hit
        tracker.record_hits(["if_1_true"])
        assert tracker.get_hit_count("if_1_true") == 1

    def test_record_multiple_hits(self) -> None:
        """Test recording multiple hits."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        tracker.record_hits(["if_1_true", "if_1_true", "if_1_true"])
        assert tracker.get_hit_count("if_1_true") == 3

    def test_record_hit_single(self) -> None:
        """Test recording a single hit."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        tracker.record_hit("if_1_true")
        assert tracker.get_hit_count("if_1_true") == 1

    def test_get_stats(self) -> None:
        """Test getting coverage stats."""
        source = """{% if show %}
Content
{% else %}
Other
{% endif %}"""
        tracker = TemplateCoverage(source, "test.j2")

        # Hit true branch
        tracker.record_hits(["if_1_true"])

        stats = tracker.get_stats()
        assert stats.template_path == "test.j2"
        assert stats.total_branches == 2
        assert stats.covered_branches == 1
        assert stats.coverage_percent == 50.0

    def test_get_stats_full_coverage(self) -> None:
        """Test getting stats with full coverage."""
        source = """{% if show %}
Content
{% else %}
Other
{% endif %}"""
        tracker = TemplateCoverage(source)

        # Hit both branches
        tracker.record_hits(["if_1_true", "if_1_false"])

        stats = tracker.get_stats()
        assert stats.coverage_percent == 100.0

    def test_reset(self) -> None:
        """Test resetting hit counts."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        tracker.record_hits(["if_1_true"])
        assert tracker.get_hit_count("if_1_true") == 1

        tracker.reset()
        assert tracker.get_hit_count("if_1_true") == 0

    def test_branch_ids(self) -> None:
        """Test getting branch IDs."""
        source = """{% if a %}
{% for b in items %}
{{ b }}
{% endfor %}
{% endif %}"""
        tracker = TemplateCoverage(source)

        branch_ids = tracker.branch_ids
        assert "if_1_true" in branch_ids
        assert "if_1_false" in branch_ids
        assert "for_2_body" in branch_ids

    def test_discovery_property(self) -> None:
        """Test accessing discovery result."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        assert tracker.discovery is not None
        assert tracker.discovery.branch_count == 2

    def test_unknown_branch_id(self) -> None:
        """Test recording unknown branch ID is ignored."""
        source = """{% if show %}
Content
{% endif %}"""
        tracker = TemplateCoverage(source)

        # Should not raise
        tracker.record_hit("unknown_branch")
        assert tracker.get_hit_count("unknown_branch") == 0
