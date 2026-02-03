"""Tests for coverage reporters."""

import json
import tempfile
from pathlib import Path

import pytest

from jinjatest.coverage.collector import CoverageSummary
from jinjatest.coverage.discovery import BranchInfo
from jinjatest.coverage.reporter import (
    CoverageReporter,
    HTMLReporter,
    JSONReporter,
    ReportConfig,
    TerminalReporter,
)
from jinjatest.coverage.tracker import BranchCoverage, TemplateCoverageStats


@pytest.fixture
def sample_stats() -> list[TemplateCoverageStats]:
    """Create sample template stats."""
    branch1 = BranchInfo("if_1_true", "if_true", 1, "if condition at line 1 is true")
    branch2 = BranchInfo("if_1_false", "if_false", 1, "if condition at line 1 is false")
    branch3 = BranchInfo("for_5_body", "for_body", 5, "for loop at line 5 has items")

    stats1 = TemplateCoverageStats(
        template_path="test1.j2",
        total_branches=2,
        covered_branches=1,
        branch_details=[
            BranchCoverage(branch=branch1, hit_count=3),
            BranchCoverage(branch=branch2, hit_count=0),
        ],
    )
    stats2 = TemplateCoverageStats(
        template_path="test2.j2",
        total_branches=1,
        covered_branches=1,
        branch_details=[
            BranchCoverage(branch=branch3, hit_count=5),
        ],
    )
    return [stats1, stats2]


@pytest.fixture
def sample_summary(sample_stats: list[TemplateCoverageStats]) -> CoverageSummary:
    """Create sample coverage summary."""
    return CoverageSummary(templates=sample_stats)


class TestReportConfig:
    """Tests for ReportConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = ReportConfig()
        assert config.fail_under == 0.0
        assert config.show_missing is True
        assert config.verbose is False


class TestTerminalReporter:
    """Tests for TerminalReporter class."""

    def test_empty_report(self) -> None:
        """Test report with no templates."""
        reporter = TerminalReporter()
        summary = CoverageSummary(templates=[])

        report = reporter.report(summary)

        assert "No templates tracked" in report

    def test_basic_report(self, sample_summary: CoverageSummary) -> None:
        """Test basic terminal report."""
        reporter = TerminalReporter()

        report = reporter.report(sample_summary)

        assert "JINJA TEMPLATE COVERAGE" in report
        assert "test1.j2" in report
        assert "test2.j2" in report
        assert "TOTAL" in report
        assert "66.7%" in report  # 2/3 branches covered

    def test_verbose_report(self, sample_summary: CoverageSummary) -> None:
        """Test verbose terminal report shows missing branches."""
        config = ReportConfig(verbose=True, show_missing=True)
        reporter = TerminalReporter(config)

        report = reporter.report(sample_summary)

        assert "if_1_false" in report

    def test_fail_under_pass(self, sample_summary: CoverageSummary) -> None:
        """Test fail_under message when passing."""
        config = ReportConfig(fail_under=50.0)
        reporter = TerminalReporter(config)

        report = reporter.report(sample_summary)

        assert "OK:" in report

    def test_fail_under_fail(self, sample_summary: CoverageSummary) -> None:
        """Test fail_under message when failing."""
        config = ReportConfig(fail_under=80.0)
        reporter = TerminalReporter(config)

        report = reporter.report(sample_summary)

        assert "FAIL:" in report

    def test_truncate_path(self) -> None:
        """Test path truncation."""
        reporter = TerminalReporter()

        short = reporter._truncate_path("short.j2", 40)
        assert short == "short.j2"

        long_path = "a" * 50
        truncated = reporter._truncate_path(long_path, 40)
        assert len(truncated) == 40
        assert truncated.startswith("...")


class TestJSONReporter:
    """Tests for JSONReporter class."""

    def test_empty_report(self) -> None:
        """Test JSON report with no templates."""
        reporter = JSONReporter()
        summary = CoverageSummary(templates=[])

        report = reporter.report(summary)
        data = json.loads(report)

        assert data["summary"]["total_branches"] == 0
        assert data["summary"]["coverage_percent"] == 100.0
        assert data["templates"] == []

    def test_basic_report(self, sample_summary: CoverageSummary) -> None:
        """Test basic JSON report."""
        reporter = JSONReporter()

        report = reporter.report(sample_summary)
        data = json.loads(report)

        assert data["summary"]["total_branches"] == 3
        assert data["summary"]["covered_branches"] == 2
        assert data["summary"]["template_count"] == 2
        assert len(data["templates"]) == 2

    def test_report_with_missing_branches(
        self, sample_summary: CoverageSummary
    ) -> None:
        """Test JSON report includes uncovered branches."""
        config = ReportConfig(show_missing=True)
        reporter = JSONReporter(config)

        report = reporter.report(sample_summary)
        data = json.loads(report)

        # test1.j2 should have uncovered branches
        test1 = next(t for t in data["templates"] if t["path"] == "test1.j2")
        assert len(test1["uncovered"]) == 1
        assert test1["uncovered"][0]["branch_id"] == "if_1_false"

    def test_fail_under_in_report(self, sample_summary: CoverageSummary) -> None:
        """Test fail_under included in JSON report."""
        config = ReportConfig(fail_under=80.0)
        reporter = JSONReporter(config)

        report = reporter.report(sample_summary)
        data = json.loads(report)

        assert data["fail_under"] == 80.0
        assert data["passed"] is False  # 66.7% < 80%

    def test_write_to_file(self, sample_summary: CoverageSummary) -> None:
        """Test writing JSON report to file."""
        reporter = JSONReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "coverage.json"
            reporter.write_to_file(sample_summary, path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert data["summary"]["total_branches"] == 3


class TestHTMLReporter:
    """Tests for HTMLReporter class."""

    def test_empty_report(self) -> None:
        """Test HTML report with no templates."""
        reporter = HTMLReporter()
        summary = CoverageSummary(templates=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            reporter.report(summary, output_dir)

            assert (output_dir / "index.html").exists()
            assert (output_dir / "style.css").exists()

    def test_basic_report(self, sample_summary: CoverageSummary) -> None:
        """Test basic HTML report."""
        reporter = HTMLReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            reporter.report(sample_summary, output_dir)

            index = (output_dir / "index.html").read_text()
            assert "test1.j2" in index
            assert "test2.j2" in index
            assert "66.7%" in index

    def test_report_with_sources(self, sample_summary: CoverageSummary) -> None:
        """Test HTML report with source files."""
        reporter = HTMLReporter()
        sources = {
            "test1.j2": "{% if x %}y{% else %}z{% endif %}",
            "test2.j2": "{% for i in items %}{{ i }}{% endfor %}",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            reporter.report(sample_summary, output_dir, sources)

            # Should have per-template pages
            assert (output_dir / "test1_j2.html").exists()
            assert (output_dir / "test2_j2.html").exists()

            # Check content
            test1_html = (output_dir / "test1_j2.html").read_text()
            assert "if x" in test1_html or "{% if x %}" in test1_html

    def test_coverage_class(self) -> None:
        """Test coverage class selection."""
        reporter = HTMLReporter()

        assert reporter._coverage_class(100) == "high"
        assert reporter._coverage_class(80) == "high"
        assert reporter._coverage_class(79) == "medium"
        assert reporter._coverage_class(50) == "medium"
        assert reporter._coverage_class(49) == "low"
        assert reporter._coverage_class(0) == "low"

    def test_safe_filename(self) -> None:
        """Test safe filename generation."""
        reporter = HTMLReporter()

        assert reporter._safe_filename("test.j2") == "test_j2"
        assert reporter._safe_filename("path/to/template.j2") == "path_to_template_j2"
        assert reporter._safe_filename(None) == "string"

    def test_escape_html(self) -> None:
        """Test HTML escaping."""
        reporter = HTMLReporter()

        assert reporter._escape("<script>") == "&lt;script&gt;"
        assert reporter._escape("a & b") == "a &amp; b"
        assert reporter._escape('"quote"') == "&quot;quote&quot;"


class TestCoverageReporter:
    """Tests for unified CoverageReporter class."""

    def test_terminal_report(self, sample_summary: CoverageSummary) -> None:
        """Test terminal report through unified reporter."""
        reporter = CoverageReporter()

        report = reporter.terminal_report(sample_summary)
        assert "JINJA TEMPLATE COVERAGE" in report

    def test_json_report(self, sample_summary: CoverageSummary) -> None:
        """Test JSON report through unified reporter."""
        reporter = CoverageReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "coverage.json"
            reporter.json_report(sample_summary, path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert "summary" in data

    def test_html_report(self, sample_summary: CoverageSummary) -> None:
        """Test HTML report through unified reporter."""
        reporter = CoverageReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            reporter.html_report(sample_summary, output_dir)

            assert (output_dir / "index.html").exists()
            assert (output_dir / "style.css").exists()

    def test_config_passed_to_reporters(self) -> None:
        """Test that config is passed to all reporters."""
        config = ReportConfig(fail_under=75.0, verbose=True)
        reporter = CoverageReporter(config)

        # Verify config is used
        assert reporter._terminal.config.fail_under == 75.0
        assert reporter._json.config.fail_under == 75.0
        assert reporter._html.config.fail_under == 75.0
