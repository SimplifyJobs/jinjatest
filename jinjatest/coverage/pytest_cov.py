"""
Pytest plugin for Jinja template coverage.

Provides CLI options and hooks for coverage collection during test runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from jinjatest.coverage.collector import (
    get_coverage_collector,
    reset_coverage_collector,
)
from jinjatest.coverage.reporter import CoverageReporter, ReportConfig

if TYPE_CHECKING:
    pass


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
            "Coverage report type: term, term-missing, term-verbose, json, html "
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


def pytest_configure(config: pytest.Config) -> None:
    """Configure coverage collection if enabled."""
    if config.getoption("--jt-cov"):
        collector = get_coverage_collector()
        collector.enable()
        config._jt_cov_enabled = True  # type: ignore[attr-defined]
    else:
        config._jt_cov_enabled = False  # type: ignore[attr-defined]


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

    fail_under = config.getoption("--jt-cov-fail-under", 0.0)
    report_types = config.getoption("--jt-cov-report", [])

    if not report_types:
        report_types = ["term"]

    report_types = [r.lower() for r in report_types]

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
        json_path = config.getoption("--jt-cov-json") or "jt-coverage.json"
        reporter.json_report(summary, Path(json_path))
        if output:
            output.line(f"JSON report written to: {json_path}")

    if "html" in report_types:
        html_dir = config.getoption("--jt-cov-html") or "jt-htmlcov"
        sources: dict[str, str] = {}
        for path, tracker in collector.get_all_trackers().items():
            if tracker.source:
                sources[path] = tracker.source
        reporter.html_report(summary, Path(html_dir), sources)
        if output:
            output.line(f"HTML report written to: {html_dir}/")

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
