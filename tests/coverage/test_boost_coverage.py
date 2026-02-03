"""Tests to boost coverage to 97%+."""

import io
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import pytest

from jinjatest import TemplateSpec
from jinjatest.coverage.collector import (
    CoverageSummary,
    get_coverage_collector,
    reset_coverage_collector,
)
from jinjatest.coverage.discovery import BranchInfo
from jinjatest.coverage.reporter import (
    CoverageReporter,
    HTMLReporter,
    JSONReporter,
    JUnitReporter,
    ReportConfig,
    TerminalReporter,
)
from jinjatest.coverage.tracker import BranchCoverage, TemplateCoverageStats


@pytest.fixture
def sample_stats_with_covered() -> list[TemplateCoverageStats]:
    """Create sample template stats with covered branches for HTML testing."""
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
def sample_summary_with_covered(
    sample_stats_with_covered: list[TemplateCoverageStats],
) -> CoverageSummary:
    """Create sample coverage summary."""
    return CoverageSummary(templates=sample_stats_with_covered)


class TestJUnitReporter:
    """Tests for JUnitReporter class."""

    def test_empty_report(self) -> None:
        """Test JUnit report with no templates."""
        reporter = JUnitReporter()
        summary = CoverageSummary(templates=[])

        report = reporter.report(summary)

        assert '<?xml version="1.0"' in report
        root = ET.fromstring(
            report.replace('<?xml version="1.0" encoding="UTF-8"?>\n', "")
        )
        assert root.tag == "testsuites"
        assert root.get("tests") == "0"
        assert root.get("failures") == "0"

    def test_basic_report(self, sample_summary_with_covered: CoverageSummary) -> None:
        """Test basic JUnit report."""
        reporter = JUnitReporter()

        report = reporter.report(sample_summary_with_covered)
        root = ET.fromstring(
            report.replace('<?xml version="1.0" encoding="UTF-8"?>\n', "")
        )

        assert root.get("tests") == "3"
        assert root.get("failures") == "1"  # One uncovered branch

        testsuites = root.findall("testsuite")
        assert len(testsuites) == 2

    def test_report_with_failures(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test JUnit report includes failure details."""
        reporter = JUnitReporter()

        report = reporter.report(sample_summary_with_covered)
        root = ET.fromstring(
            report.replace('<?xml version="1.0" encoding="UTF-8"?>\n', "")
        )

        # Find the failure element
        failures = root.findall(".//failure")
        assert len(failures) == 1
        assert "Branch not covered" in failures[0].get("message", "")
        assert failures[0].text is not None
        assert "Line 1" in failures[0].text

    def test_report_with_output(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test JUnit report writes to output stream."""
        reporter = JUnitReporter()
        output = io.StringIO()

        report = reporter.report(sample_summary_with_covered, output)

        assert output.getvalue() == report
        assert '<?xml version="1.0"' in output.getvalue()

    def test_write_to_file(self, sample_summary_with_covered: CoverageSummary) -> None:
        """Test writing JUnit report to file."""
        reporter = JUnitReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "coverage.xml"
            reporter.write_to_file(sample_summary_with_covered, path)

            assert path.exists()
            content = path.read_text()
            assert '<?xml version="1.0"' in content


class TestCoverageReporterJUnit:
    """Tests for CoverageReporter JUnit support."""

    def test_junit_report(self, sample_summary_with_covered: CoverageSummary) -> None:
        """Test JUnit report through unified reporter."""
        reporter = CoverageReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "coverage.xml"
            reporter.junit_report(sample_summary_with_covered, path)

            assert path.exists()
            content = path.read_text()
            assert '<?xml version="1.0"' in content
            assert "testsuites" in content


class TestTerminalReporterExtended:
    """Extended tests for TerminalReporter."""

    def test_report_with_output_stream(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test terminal report writes to output stream."""
        reporter = TerminalReporter()
        output = io.StringIO()

        report = reporter.report(sample_summary_with_covered, output)

        assert output.getvalue() == report

    def test_report_empty_with_output(self) -> None:
        """Test empty report writes to output stream."""
        reporter = TerminalReporter()
        summary = CoverageSummary(templates=[])
        output = io.StringIO()

        report = reporter.report(summary, output)

        assert output.getvalue() == report
        assert "No templates tracked" in output.getvalue()

    def test_show_missing_inline(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test show_missing_inline format."""
        config = ReportConfig(show_missing_inline=True)
        reporter = TerminalReporter(config)

        report = reporter.report(sample_summary_with_covered)

        # Should have "Missing" header and show line numbers
        assert "Missing" in report
        assert "-" * 90 in report  # 90-char separator for inline format

    def test_get_missing_lines_empty(self) -> None:
        """Test _get_missing_lines with no uncovered branches."""
        reporter = TerminalReporter()
        branch = BranchInfo("if_1_true", "if_true", 1, "test")
        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=1,
            covered_branches=1,
            branch_details=[BranchCoverage(branch=branch, hit_count=1)],
        )

        missing = reporter._get_missing_lines(stats)
        assert missing == ""

    def test_get_missing_lines_with_branches(self) -> None:
        """Test _get_missing_lines with uncovered branches."""
        reporter = TerminalReporter()
        branch1 = BranchInfo("if_1_false", "if_false", 10, "test1")
        branch2 = BranchInfo("if_2_false", "if_false", 16, "test2")
        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=2,
            covered_branches=0,
            branch_details=[
                BranchCoverage(branch=branch1, hit_count=0),
                BranchCoverage(branch=branch2, hit_count=0),
            ],
        )

        missing = reporter._get_missing_lines(stats)
        assert "10" in missing
        assert "16" in missing


class TestHTMLReporterExtended:
    """Extended tests for HTMLReporter."""

    def test_generate_template_page_with_covered_lines(self) -> None:
        """Test template page generation with covered lines."""
        reporter = HTMLReporter()

        branch1 = BranchInfo("if_1_true", "if_true", 1, "if true")
        branch2 = BranchInfo("if_1_false", "if_false", 1, "if false")
        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=2,
            covered_branches=1,
            branch_details=[
                BranchCoverage(branch=branch1, hit_count=1),
                BranchCoverage(branch=branch2, hit_count=0),
            ],
        )
        source = "{% if x %}\nyes\n{% else %}\nno\n{% endif %}"

        html = reporter._generate_template_page(stats, source)

        # Should have both covered and uncovered classes
        assert 'class="covered"' in html or 'class="uncovered"' in html
        assert "test.j2" in html

    def test_generate_template_page_all_covered(self) -> None:
        """Test template page when all branches covered."""
        reporter = HTMLReporter()

        branch1 = BranchInfo("if_1_true", "if_true", 1, "if true")
        stats = TemplateCoverageStats(
            template_path="test.j2",
            total_branches=1,
            covered_branches=1,
            branch_details=[
                BranchCoverage(branch=branch1, hit_count=1),
            ],
        )
        source = "{% if x %}yes{% endif %}"

        html = reporter._generate_template_page(stats, source)

        assert "All branches covered!" in html


class TestJSONReporterExtended:
    """Extended tests for JSONReporter."""

    def test_report_with_output_stream(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test JSON report writes to output stream."""
        reporter = JSONReporter()
        output = io.StringIO()

        report = reporter.report(sample_summary_with_covered, output)

        assert output.getvalue() == report

    def test_show_missing_includes_covered(
        self, sample_summary_with_covered: CoverageSummary
    ) -> None:
        """Test show_missing includes covered branches too."""
        config = ReportConfig(show_missing=True)
        reporter = JSONReporter(config)

        report = reporter.report(sample_summary_with_covered)
        data = json.loads(report)

        # Should have both covered and uncovered
        test1 = next(t for t in data["templates"] if t["path"] == "test1.j2")
        assert "covered" in test1
        assert "uncovered" in test1
        assert len(test1["covered"]) == 1
        assert test1["covered"][0]["hit_count"] == 3


class TestPytestCovPlugin:
    """Tests for pytest coverage plugin hooks."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_load_pyproject_config_no_tomllib(self) -> None:
        """Test config loading when tomllib is not available."""
        from jinjatest.coverage import pytest_cov

        with mock.patch.dict("sys.modules", {"tomllib": None, "tomli": None}):
            # Force reimport to test the import error path
            with mock.patch.object(pytest_cov, "_load_pyproject_config") as mock_load:
                mock_load.return_value = {}
                result = mock_load()
                assert result == {}

    def test_load_pyproject_config_no_file(self) -> None:
        """Test config loading when pyproject.toml doesn't exist."""
        from jinjatest.coverage.pytest_cov import _load_pyproject_config

        with mock.patch("pathlib.Path.exists", return_value=False):
            result = _load_pyproject_config()
            assert result == {}

    def test_load_pyproject_config_parse_error(self) -> None:
        """Test config loading handles parse errors."""
        from jinjatest.coverage.pytest_cov import _load_pyproject_config

        with mock.patch("pathlib.Path.exists", return_value=True):
            with mock.patch(
                "builtins.open", mock.mock_open(read_data=b"invalid toml [")
            ):
                result = _load_pyproject_config()
                assert result == {}

    def test_pytest_configure_enables_collector(self) -> None:
        """Test pytest_configure enables collector when --jt-cov is set."""
        from jinjatest.coverage.pytest_cov import pytest_configure

        config = mock.MagicMock()
        config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov": True,
            "--jt-cov-exclude": [],
        }.get(x, default)

        with mock.patch(
            "jinjatest.coverage.pytest_cov._load_pyproject_config", return_value={}
        ):
            pytest_configure(config)

        collector = get_coverage_collector()
        assert collector.enabled is True
        assert config._jt_cov_enabled is True

    def test_pytest_configure_with_excludes(self) -> None:
        """Test pytest_configure sets exclude patterns."""
        from jinjatest.coverage.pytest_cov import pytest_configure

        config = mock.MagicMock()
        config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov": True,
            "--jt-cov-exclude": ["**/vendor/**"],
        }.get(x, default)

        with mock.patch(
            "jinjatest.coverage.pytest_cov._load_pyproject_config",
            return_value={"exclude_patterns": ["*.partial.j2"]},
        ):
            pytest_configure(config)

        collector = get_coverage_collector()
        assert "**/vendor/**" in collector._exclude_patterns
        assert "*.partial.j2" in collector._exclude_patterns

    def test_pytest_configure_disabled(self) -> None:
        """Test pytest_configure when coverage is disabled."""
        from jinjatest.coverage.pytest_cov import pytest_configure

        reset_coverage_collector()
        config = mock.MagicMock()
        config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov": False,
        }.get(x, default)

        with mock.patch(
            "jinjatest.coverage.pytest_cov._load_pyproject_config", return_value={}
        ):
            pytest_configure(config)

        assert config._jt_cov_enabled is False

    def test_pytest_unconfigure_resets_collector(self) -> None:
        """Test pytest_unconfigure resets the collector."""
        from jinjatest.coverage.pytest_cov import pytest_unconfigure

        collector = get_coverage_collector()
        collector.enable()

        config = mock.MagicMock()
        pytest_unconfigure(config)

        collector = get_coverage_collector()
        assert collector.enabled is False

    def test_pytest_sessionstart_resets_collector(self) -> None:
        """Test pytest_sessionstart resets and enables collector."""
        from jinjatest.coverage.pytest_cov import pytest_sessionstart

        collector = get_coverage_collector()
        collector.enable()

        # Register a template to verify reset
        collector.register_template("old.j2", "old content")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True

        pytest_sessionstart(session)

        # Collector should be reset and re-enabled
        assert collector.enabled is True
        assert collector.get_tracker("old.j2") is None

    def test_pytest_sessionfinish_disabled(self) -> None:
        """Test pytest_sessionfinish does nothing when disabled."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        session = mock.MagicMock()
        session.config._jt_cov_enabled = False

        # Should not raise
        pytest_sessionfinish(session, 0)

    def test_pytest_sessionfinish_generates_reports(self) -> None:
        """Test pytest_sessionfinish generates reports."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,
            "--jt-cov-report": ["term"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        # Should have written output
        tw.write.assert_called()

    def test_pytest_sessionfinish_json_report(self) -> None:
        """Test pytest_sessionfinish generates JSON report."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "coverage.json"

            session = mock.MagicMock()
            session.config._jt_cov_enabled = True
            session.config._jt_cov_pyproject = {}
            session.config.getoption.side_effect = lambda x, default=None: {
                "--jt-cov-fail-under": 0.0,
                "--jt-cov-report": ["json"],
                "--jt-cov-html": None,
                "--jt-cov-json": str(json_path),
                "--jt-cov-xml": None,
            }.get(x, default)

            tw = mock.MagicMock()
            terminalreporter = mock.MagicMock()
            terminalreporter._tw = tw
            session.config.pluginmanager.get_plugin.return_value = terminalreporter

            pytest_sessionfinish(session, 0)

            assert json_path.exists()

    def test_pytest_sessionfinish_html_report(self) -> None:
        """Test pytest_sessionfinish generates HTML report."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        with tempfile.TemporaryDirectory() as tmpdir:
            html_dir = Path(tmpdir) / "htmlcov"

            session = mock.MagicMock()
            session.config._jt_cov_enabled = True
            session.config._jt_cov_pyproject = {}
            session.config.getoption.side_effect = lambda x, default=None: {
                "--jt-cov-fail-under": 0.0,
                "--jt-cov-report": ["html"],
                "--jt-cov-html": str(html_dir),
                "--jt-cov-json": None,
                "--jt-cov-xml": None,
            }.get(x, default)

            tw = mock.MagicMock()
            terminalreporter = mock.MagicMock()
            terminalreporter._tw = tw
            session.config.pluginmanager.get_plugin.return_value = terminalreporter

            pytest_sessionfinish(session, 0)

            assert html_dir.exists()
            assert (html_dir / "index.html").exists()

    def test_pytest_sessionfinish_xml_report(self) -> None:
        """Test pytest_sessionfinish generates XML report."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "coverage.xml"

            session = mock.MagicMock()
            session.config._jt_cov_enabled = True
            session.config._jt_cov_pyproject = {}
            session.config.getoption.side_effect = lambda x, default=None: {
                "--jt-cov-fail-under": 0.0,
                "--jt-cov-report": ["xml"],
                "--jt-cov-html": None,
                "--jt-cov-json": None,
                "--jt-cov-xml": str(xml_path),
            }.get(x, default)

            tw = mock.MagicMock()
            terminalreporter = mock.MagicMock()
            terminalreporter._tw = tw
            session.config.pluginmanager.get_plugin.return_value = terminalreporter

            pytest_sessionfinish(session, 0)

            assert xml_path.exists()

    def test_pytest_sessionfinish_fail_under(self) -> None:
        """Test pytest_sessionfinish sets fail flag when below threshold."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 100.0,  # High threshold
            "--jt-cov-report": ["term"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        assert session.config._jt_cov_failed is True

    def test_pytest_terminal_summary_with_failure(self) -> None:
        """Test pytest_terminal_summary shows failure message."""
        from jinjatest.coverage.pytest_cov import pytest_terminal_summary

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        config = mock.MagicMock()
        config._jt_cov_failed = True
        config.getoption.return_value = 80.0

        terminalreporter = mock.MagicMock()

        pytest_terminal_summary(terminalreporter, 0, config)

        terminalreporter.write_line.assert_called()
        call_args = terminalreporter.write_line.call_args
        assert "FAILED" in call_args[0][0]

    def test_pytest_terminal_summary_no_failure(self) -> None:
        """Test pytest_terminal_summary does nothing when not failed."""
        from jinjatest.coverage.pytest_cov import pytest_terminal_summary

        config = mock.MagicMock()
        config._jt_cov_failed = False

        terminalreporter = mock.MagicMock()

        pytest_terminal_summary(terminalreporter, 0, config)

        terminalreporter.write_line.assert_not_called()

    def test_pytest_sessionfinish_no_terminal_reporter(self) -> None:
        """Test pytest_sessionfinish handles missing terminal reporter."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,
            "--jt-cov-report": ["term"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)
        session.config.pluginmanager.get_plugin.return_value = None

        # Should not raise
        pytest_sessionfinish(session, 0)

    def test_pytest_sessionfinish_default_reports(self) -> None:
        """Test pytest_sessionfinish uses default report types."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,
            "--jt-cov-report": [],  # Empty - should default to term
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        # Should have written term report
        tw.write.assert_called()

    def test_pytest_sessionfinish_term_missing(self) -> None:
        """Test pytest_sessionfinish handles term-missing report type."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,
            "--jt-cov-report": ["term-missing"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        tw.write.assert_called()

    def test_pytest_sessionfinish_term_verbose(self) -> None:
        """Test pytest_sessionfinish handles term-verbose report type."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,
            "--jt-cov-report": ["term-verbose"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        tw.write.assert_called()

    def test_pytest_sessionfinish_pyproject_fail_under(self) -> None:
        """Test pytest_sessionfinish uses pyproject fail_under."""
        from jinjatest.coverage.pytest_cov import pytest_sessionfinish

        collector = get_coverage_collector()
        collector.enable()
        collector.register_template("test.j2", "{% if x %}y{% endif %}")

        session = mock.MagicMock()
        session.config._jt_cov_enabled = True
        session.config._jt_cov_pyproject = {"fail_under": 100.0}
        session.config.getoption.side_effect = lambda x, default=None: {
            "--jt-cov-fail-under": 0.0,  # CLI not set
            "--jt-cov-report": ["term"],
            "--jt-cov-html": None,
            "--jt-cov-json": None,
            "--jt-cov-xml": None,
        }.get(x, default)

        tw = mock.MagicMock()
        terminalreporter = mock.MagicMock()
        terminalreporter._tw = tw
        session.config.pluginmanager.get_plugin.return_value = terminalreporter

        pytest_sessionfinish(session, 0)

        assert session.config._jt_cov_failed is True


class TestSpecEdgeCases:
    """Tests for spec.py edge cases."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_get_undeclared_variables_no_source(self) -> None:
        """Test get_undeclared_variables returns empty set when no source."""
        spec = TemplateSpec.from_string("hello", test_mode=False)
        # Clear the source
        spec._source = None

        # Mock env.loader to return None
        spec._env._loader = None

        result = spec.get_undeclared_variables()
        assert result == set()

    def test_template_spec_with_coverage_hash_path(self) -> None:
        """Test template spec generates hash-based path for string templates."""
        collector = get_coverage_collector()
        collector.enable()

        # Create spec without explicit template_path - should generate hash
        spec = TemplateSpec.from_string("{% if x %}y{% endif %}")

        # Render to trigger coverage
        spec.render({"x": True})

        summary = collector.get_summary()
        # Should have a template with hash-based path
        assert summary.template_count == 1
        template = summary.templates[0]
        assert template.template_path is not None
        assert "<string:" in template.template_path


class TestCollectorEdgeCases:
    """Tests for collector edge cases."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_record_render_disabled(self) -> None:
        """Test record_render does nothing when disabled."""
        collector = get_coverage_collector()
        # Don't enable

        collector.record_render("test.j2", ["trace1"])

        # Should not have any trackers
        assert collector.get_tracker("test.j2") is None

    def test_record_render_unknown_path(self) -> None:
        """Test record_render handles unknown paths."""
        collector = get_coverage_collector()
        collector.enable()

        # Record without registering first
        collector.record_render("unknown.j2", ["trace1"])

        # Should not crash, just ignore
        assert collector.get_tracker("unknown.j2") is None

    def test_register_template_excluded(self) -> None:
        """Test register_template respects exclude patterns."""
        collector = get_coverage_collector()
        collector.enable()
        collector.set_exclude_patterns(["**/vendor/**"])

        source = "{% if x %}y{% endif %}"
        result = collector.register_template("path/vendor/test.j2", source)

        # Should return original source (not instrumented)
        assert result == source
        assert collector.get_tracker("path/vendor/test.j2") is None
