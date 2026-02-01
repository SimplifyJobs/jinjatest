"""
Coverage collector for aggregating coverage across multiple templates.

This module provides a global singleton collector that can be used
during pytest sessions to track coverage across all template renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from jinjatest.coverage.tracker import TemplateCoverage, TemplateCoverageStats

if TYPE_CHECKING:
    pass


@dataclass
class CoverageSummary:
    """Aggregated coverage summary across all templates."""

    templates: list[TemplateCoverageStats]
    total_branches: int = 0
    covered_branches: int = 0

    def __post_init__(self) -> None:
        """Calculate totals from template stats."""
        self.total_branches = sum(t.total_branches for t in self.templates)
        self.covered_branches = sum(t.covered_branches for t in self.templates)

    @property
    def coverage_percent(self) -> float:
        """Get overall coverage percentage (0-100)."""
        if self.total_branches == 0:
            return 100.0
        return (self.covered_branches / self.total_branches) * 100

    @property
    def template_count(self) -> int:
        """Get number of templates tracked."""
        return len(self.templates)

    def get_template_stats(self, path: str) -> TemplateCoverageStats | None:
        """Get stats for a specific template.

        Args:
            path: The template path.

        Returns:
            TemplateCoverageStats or None if not found.
        """
        for stats in self.templates:
            if stats.template_path == path:
                return stats
        return None


class CoverageCollector:
    """Global collector for tracking template coverage.

    Thread-safe singleton that aggregates coverage data across
    all template renders during a test session.

    Example:
        >>> collector = get_coverage_collector()
        >>> instrumented = collector.register_template("my.j2", source)
        >>> # ... render template ...
        >>> collector.record_render("my.j2", trace_events)
        >>> summary = collector.get_summary()
    """

    def __init__(self) -> None:
        """Initialize the coverage collector."""
        self._trackers: dict[str, TemplateCoverage] = {}
        self._lock = Lock()
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if coverage collection is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable coverage collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable coverage collection."""
        self._enabled = False

    def reset(self) -> None:
        """Reset all coverage data."""
        with self._lock:
            self._trackers.clear()

    def register_template(
        self,
        path: str,
        source: str,
    ) -> str:
        """Register a template for coverage tracking.

        Args:
            path: The template path (used as identifier).
            source: The template source code.

        Returns:
            The instrumented source code.
        """
        if not self._enabled:
            return source

        with self._lock:
            if path not in self._trackers:
                tracker = TemplateCoverage(source, path)
                self._trackers[path] = tracker

            return self._trackers[path].instrumented_source

    def record_render(
        self,
        path: str,
        trace_events: list[str],
    ) -> None:
        """Record coverage data from a template render.

        Args:
            path: The template path.
            trace_events: List of trace events from the render.
        """
        if not self._enabled:
            return

        with self._lock:
            if path in self._trackers:
                self._trackers[path].record_hits(trace_events)

    def get_tracker(self, path: str) -> TemplateCoverage | None:
        """Get the tracker for a specific template.

        Args:
            path: The template path.

        Returns:
            TemplateCoverage or None if not registered.
        """
        with self._lock:
            return self._trackers.get(path)

    def get_summary(self) -> CoverageSummary:
        """Get aggregated coverage summary.

        Returns:
            CoverageSummary with stats for all templates.
        """
        with self._lock:
            template_stats = [
                tracker.get_stats() for tracker in self._trackers.values()
            ]

        return CoverageSummary(templates=template_stats)

    def get_all_trackers(self) -> dict[str, TemplateCoverage]:
        """Get all registered trackers.

        Returns:
            Dictionary mapping paths to trackers.
        """
        with self._lock:
            return dict(self._trackers)


# Global singleton instance
_collector: CoverageCollector | None = None
_collector_lock = Lock()


def get_coverage_collector() -> CoverageCollector:
    """Get the global coverage collector singleton.

    Returns:
        The global CoverageCollector instance.
    """
    global _collector
    with _collector_lock:
        if _collector is None:
            _collector = CoverageCollector()
        return _collector


def set_coverage_collector(collector: CoverageCollector | None) -> None:
    """Set the global coverage collector.

    Useful for testing or resetting state.

    Args:
        collector: The collector to set, or None to reset.
    """
    global _collector
    with _collector_lock:
        _collector = collector


def reset_coverage_collector() -> None:
    """Reset the global coverage collector to a fresh state."""
    global _collector
    with _collector_lock:
        if _collector is not None:
            _collector.reset()
            _collector.disable()
