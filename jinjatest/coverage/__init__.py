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
from jinjatest.coverage.loader import (
    CoverageLoader,
    unwrap_loader,
)
from jinjatest.coverage.reporter import (
    CoverageReporter,
    HTMLReporter,
    JSONReporter,
    JUnitReporter,
    ReportConfig,
    TerminalReporter,
)
from jinjatest.coverage.tracker import (
    BranchCoverage,
    TemplateCoverage,
    TemplateCoverageStats,
)
from jinjatest.coverage.types import (
    BranchType,
    CoverageConfig,
    ReportType,
)

__all__ = [
    "AutoInstrumenter",
    "BranchCoverage",
    "BranchDiscovery",
    "BranchInfo",
    "BranchType",
    "CoverageCollector",
    "CoverageConfig",
    "CoverageLoader",
    "CoverageReporter",
    "CoverageSummary",
    "DiscoveryResult",
    "HTMLReporter",
    "InstrumentationResult",
    "JSONReporter",
    "JUnitReporter",
    "ReportConfig",
    "ReportType",
    "TemplateCoverage",
    "TemplateCoverageStats",
    "TerminalReporter",
    "get_coverage_collector",
    "reset_coverage_collector",
    "set_coverage_collector",
    "unwrap_loader",
]
