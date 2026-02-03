"""
Pytest plugin for Jinja template coverage.

Provides CLI options and hooks for coverage collection during test runs.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from jinjatest.coverage.collector import (
    get_coverage_collector,
    reset_coverage_collector,
)
from jinjatest.coverage.reporter import CoverageReporter, ReportConfig
from jinjatest.coverage.types import (
    CoverageConfig,
    ReportType,
    _normalize_and_validate_report_type,
)


def _load_pyproject_config() -> CoverageConfig:
    """Load coverage configuration from pyproject.toml.

    Returns:
        CoverageConfig instance with settings from pyproject.toml or defaults.
    """
    tomllib: ModuleType | None = None
    try:
        import tomllib as _tomllib  # type: ignore[import-not-found]

        tomllib = _tomllib
    except ImportError:
        try:
            import tomli as _tomli  # type: ignore[import-not-found]

            tomllib = _tomli
        except ImportError:
            return CoverageConfig()

    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        return CoverageConfig()

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        raw_config: dict[str, Any] = (
            data.get("tool", {}).get("jinjatest", {}).get("coverage", {})
        )
        return CoverageConfig.model_validate(raw_config)
    except (ValidationError, Exception):
        return CoverageConfig()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for jinja template coverage."""
    group = parser.getgroup("jinjatest-cov", "Jinja template coverage")

    group.addoption(
        "--jt-cov",
        action="store_true",
        default=False,
        help="Enable Jinja template branch coverage tracking",
    )

    group.addoption(
        "--jt-cov-fail-under",
        action="store",
        type=float,
        default=0.0,
        metavar="MIN",
        help="Fail if template coverage is below MIN percent",
    )

    group.addoption(
        "--jt-cov-report",
        action="append",
        default=[],
        metavar="TYPE",
        help=(
            "Coverage report type: term, term-missing, term-verbose, json, html, xml "
            "(can be specified multiple times)"
        ),
    )

    group.addoption(
        "--jt-cov-html",
        action="store",
        default=None,
        metavar="DIR",
        help="Directory for HTML coverage report (default: jt-htmlcov)",
    )

    group.addoption(
        "--jt-cov-json",
        action="store",
        default=None,
        metavar="FILE",
        help="File for JSON coverage report (default: jt-coverage.json)",
    )

    group.addoption(
        "--jt-cov-xml",
        action="store",
        default=None,
        metavar="FILE",
        help="File for JUnit XML coverage report (default: jt-coverage.xml)",
    )

    group.addoption(
        "--jt-cov-exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern to exclude templates from coverage (can be specified multiple times)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure coverage collection if enabled."""
    pyproject_config = _load_pyproject_config()

    cov_enabled = config.getoption("--jt-cov") or pyproject_config.enabled

    if cov_enabled:
        collector = get_coverage_collector()
        collector.enable()

        cli_excludes: list[str] = config.getoption("--jt-cov-exclude", [])
        all_excludes = cli_excludes + pyproject_config.exclude_patterns
        if all_excludes:
            collector.set_exclude_patterns(all_excludes)

        config._jt_cov_enabled = True  # type: ignore[attr-defined]
        config._jt_cov_pyproject = pyproject_config  # type: ignore[attr-defined]
    else:
        config._jt_cov_enabled = False  # type: ignore[attr-defined]
        config._jt_cov_pyproject = CoverageConfig()  # type: ignore[attr-defined]


def pytest_unconfigure(config: pytest.Config) -> None:
    """Clean up coverage collector."""
    reset_coverage_collector()


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    """Generate coverage reports at end of session."""
    config = session.config

    if not getattr(config, "_jt_cov_enabled", False):
        return

    collector = get_coverage_collector()
    summary = collector.get_summary()
    pyproject_config: CoverageConfig = getattr(
        config, "_jt_cov_pyproject", CoverageConfig()
    )

    cli_fail_under: float = config.getoption("--jt-cov-fail-under", 0.0)
    fail_under = cli_fail_under if cli_fail_under > 0 else pyproject_config.fail_under

    cli_report_types: list[str] = config.getoption("--jt-cov-report", [])
    if cli_report_types:
        report_types: list[ReportType] = [
            _normalize_and_validate_report_type(rt) for rt in cli_report_types
        ]
    else:
        report_types = pyproject_config.report

    if not report_types:
        report_types = ["term"]

    report_config = ReportConfig(
        fail_under=fail_under,
        show_missing=True,
        verbose="term-verbose" in report_types,
        show_missing_inline="term-missing" in report_types,
    )
    reporter = CoverageReporter(report_config)

    terminalreporter = config.pluginmanager.get_plugin("terminalreporter")
    output = terminalreporter._tw if terminalreporter else None

    if (
        "term" in report_types
        or "term-missing" in report_types
        or "term-verbose" in report_types
    ):
        report_text = reporter.terminal_report(summary)
        if output:
            output.write(report_text)
            output.line()

    if "json" in report_types:
        cli_json_path = config.getoption("--jt-cov-json")
        json_path = cli_json_path or pyproject_config.json_file
        reporter.json_report(summary, Path(json_path))
        if output:
            output.line(f"JSON report written to: {json_path}")

    if "html" in report_types:
        cli_html_dir = config.getoption("--jt-cov-html")
        html_dir = cli_html_dir or pyproject_config.html_dir
        sources: dict[str, str] = {}
        for path, tracker in collector.get_all_trackers().items():
            if tracker.source:
                sources[path] = tracker.source
        reporter.html_report(summary, Path(html_dir), sources)
        if output:
            output.line(f"HTML report written to: {html_dir}/")

    if "xml" in report_types:
        cli_xml_path = config.getoption("--jt-cov-xml")
        xml_path = cli_xml_path or pyproject_config.xml_file
        reporter.junit_report(summary, Path(xml_path))
        if output:
            output.line(f"JUnit XML report written to: {xml_path}")

    if fail_under > 0 and summary.coverage_percent < fail_under:
        session.config._jt_cov_failed = True  # type: ignore[attr-defined]


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Add coverage failure message to terminal summary."""
    if getattr(config, "_jt_cov_failed", False):
        collector = get_coverage_collector()
        summary = collector.get_summary()
        fail_under = config.getoption("--jt-cov-fail-under", 0.0)

        terminalreporter.write_line(
            f"\nFAILED: Jinja template coverage {summary.coverage_percent:.1f}% "
            f"< required {fail_under:.1f}%",
            red=True,
            bold=True,
        )


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Reset coverage at session start."""
    if getattr(session.config, "_jt_cov_enabled", False):
        collector = get_coverage_collector()
        collector.reset()
        collector.enable()
