"""
Jinja template branch coverage tracking.

This module provides automatic branch coverage tracking for Jinja templates.

Example:
    from jinjatest.coverage import (
        get_coverage_collector,
        CoverageReporter,
        ReportConfig,
    )

    # Enable coverage collection
    collector = get_coverage_collector()
    collector.enable()

    # ... run tests with TemplateSpec ...

    # Generate reports
    summary = collector.get_summary()
    reporter = CoverageReporter(ReportConfig(fail_under=80))
    reporter.terminal_report(summary)
"""

from jinjatest.coverage.collector import (
    CoverageCollector,
    CoverageSummary,
    get_coverage_collector,
    reset_coverage_collector,
    set_coverage_collector,
)
from jinjatest.coverage.discovery import (
    BranchDiscovery,
    BranchInfo,
    DiscoveryResult,
)
from jinjatest.coverage.instrumenter import (
    AutoInstrumenter,
    InstrumentationResult,
)
from jinjatest.coverage.reporter import (
    CoverageReporter,
    HTMLReporter,
    JSONReporter,
    ReportConfig,
    TerminalReporter,
)
from jinjatest.coverage.tracker import (
    BranchCoverage,
    TemplateCoverage,
    TemplateCoverageStats,
)

__all__ = [
    "CoverageCollector",
    "CoverageSummary",
    "get_coverage_collector",
    "set_coverage_collector",
    "reset_coverage_collector",
    "BranchDiscovery",
    "BranchInfo",
    "DiscoveryResult",
    "AutoInstrumenter",
    "InstrumentationResult",
    "TemplateCoverage",
    "TemplateCoverageStats",
    "BranchCoverage",
    "CoverageReporter",
    "TerminalReporter",
    "JSONReporter",
    "HTMLReporter",
    "ReportConfig",
]
