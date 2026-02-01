"""
Template coverage tracking.

This module provides the TemplateCoverage class that combines
discovery and instrumentation to track coverage for a single template.
"""

from __future__ import annotations

from dataclasses import dataclass

from jinjatest.coverage.discovery import BranchInfo, DiscoveryResult
from jinjatest.coverage.instrumenter import AutoInstrumenter


@dataclass
class BranchCoverage:
    """Coverage information for a single branch."""

    branch: BranchInfo
    hit_count: int = 0

    @property
    def was_hit(self) -> bool:
        """Check if this branch was executed at least once."""
        return self.hit_count > 0


@dataclass
class TemplateCoverageStats:
    """Coverage statistics for a template."""

    template_path: str | None
    total_branches: int
    covered_branches: int
    branch_details: list[BranchCoverage]

    @property
    def coverage_percent(self) -> float:
        """Get coverage percentage (0-100)."""
        if self.total_branches == 0:
            return 100.0
        return (self.covered_branches / self.total_branches) * 100

    @property
    def uncovered_branches(self) -> list[BranchCoverage]:
        """Get list of branches that were not covered."""
        return [b for b in self.branch_details if not b.was_hit]

    @property
    def covered_branch_list(self) -> list[BranchCoverage]:
        """Get list of branches that were covered."""
        return [b for b in self.branch_details if b.was_hit]


class TemplateCoverage:
    """Tracks branch coverage for a single template.

    Combines branch discovery and instrumentation to provide
    coverage tracking for a template.

    Example:
        >>> tracker = TemplateCoverage(source, "my_template.j2")
        >>> instrumented = tracker.instrumented_source
        >>> # ... render template and get trace events ...
        >>> tracker.record_hits(trace_events)
        >>> stats = tracker.get_stats()
        >>> print(f"Coverage: {stats.coverage_percent:.1f}%")
    """

    def __init__(
        self,
        source: str,
        template_path: str | None = None,
    ) -> None:
        """Initialize coverage tracking for a template.

        Args:
            source: The template source code.
            template_path: Optional path for identification in reports.
        """
        self._source = source
        self._template_path = template_path

        self._instrumenter = AutoInstrumenter()
        self._instrumentation_result = self._instrumenter.instrument(
            source, template_path
        )

        self._hits: dict[str, int] = {
            branch.branch_id: 0
            for branch in self._instrumentation_result.discovery.branches
        }

    @property
    def source(self) -> str:
        """Get the original template source."""
        return self._source

    @property
    def instrumented_source(self) -> str:
        """Get the instrumented template source."""
        return self._instrumentation_result.source

    @property
    def discovery(self) -> DiscoveryResult:
        """Get the branch discovery result."""
        return self._instrumentation_result.discovery

    @property
    def template_path(self) -> str | None:
        """Get the template path."""
        return self._template_path

    @property
    def branch_ids(self) -> set[str]:
        """Get all branch IDs for this template."""
        return self._instrumentation_result.discovery.branch_ids

    def record_hits(self, trace_events: list[str]) -> None:
        """Record branch hits from trace events.

        Args:
            trace_events: List of trace events from a template render.
        """
        for event in trace_events:
            if event in self._hits:
                self._hits[event] += 1

    def record_hit(self, branch_id: str) -> None:
        """Record a single branch hit.

        Args:
            branch_id: The branch ID that was hit.
        """
        if branch_id in self._hits:
            self._hits[branch_id] += 1

    def get_hit_count(self, branch_id: str) -> int:
        """Get the hit count for a branch.

        Args:
            branch_id: The branch ID.

        Returns:
            Number of times the branch was hit.
        """
        return self._hits.get(branch_id, 0)

    def get_stats(self) -> TemplateCoverageStats:
        """Get coverage statistics.

        Returns:
            TemplateCoverageStats with coverage information.
        """
        branch_details = [
            BranchCoverage(
                branch=branch,
                hit_count=self._hits.get(branch.branch_id, 0),
            )
            for branch in self._instrumentation_result.discovery.branches
        ]

        covered = sum(1 for b in branch_details if b.was_hit)

        return TemplateCoverageStats(
            template_path=self._template_path,
            total_branches=len(branch_details),
            covered_branches=covered,
            branch_details=branch_details,
        )

    def reset(self) -> None:
        """Reset all hit counts to zero."""
        for branch_id in self._hits:
            self._hits[branch_id] = 0
