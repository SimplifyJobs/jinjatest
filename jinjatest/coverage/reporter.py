"""
Coverage reporters for terminal, JSON, and HTML output.

This module provides different report formats for coverage data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from jinjatest.coverage._templates import (
    INDEX_HTML,
    ROW_HTML,
    SOURCE_LINE_HTML,
    STYLE_CSS,
    TEMPLATE_PAGE_HTML,
)

if TYPE_CHECKING:
    from jinjatest.coverage.collector import CoverageSummary
    from jinjatest.coverage.tracker import TemplateCoverageStats


@dataclass
class ReportConfig:
    """Configuration for coverage reports."""

    fail_under: float = 0.0
    show_missing: bool = True
    verbose: bool = False
    show_missing_inline: bool = False


class TerminalReporter:
    """Terminal coverage reporter.

    Outputs coverage information to the terminal in a tabular format.
    """

    def __init__(self, config: ReportConfig | None = None) -> None:
        """Initialize the terminal reporter.

        Args:
            config: Optional report configuration.
        """
        self.config = config or ReportConfig()

    def report(
        self,
        summary: CoverageSummary,
        output: TextIO | None = None,
    ) -> str:
        """Generate a terminal coverage report.

        Args:
            summary: The coverage summary to report.
            output: Optional file-like object to write to.

        Returns:
            The formatted report string.
        """
        lines: list[str] = []

        lines.append("")
        lines.append("=" * 70)
        lines.append("JINJA TEMPLATE COVERAGE")
        lines.append("=" * 70)
        lines.append("")

        if not summary.templates:
            lines.append("No templates tracked.")
            lines.append("")
            result = "\n".join(lines)
            if output:
                output.write(result)
            return result

        # Determine column layout based on mode
        if self.config.show_missing_inline:
            lines.append(
                f"{'Template':<40} {'Branches':>8} {'Covered':>8} "
                f"{'Coverage':>8}   {'Missing'}"
            )
            lines.append("-" * 90)
        else:
            lines.append(
                f"{'Template':<40} {'Branches':>10} {'Covered':>10} {'Coverage':>10}"
            )
            lines.append("-" * 70)

        for stats in sorted(summary.templates, key=lambda s: s.template_path or ""):
            path = self._truncate_path(stats.template_path or "<string>", 40)

            if self.config.show_missing_inline:
                missing_lines = self._get_missing_lines(stats)
                lines.append(
                    f"{path:<40} {stats.total_branches:>8} "
                    f"{stats.covered_branches:>8} {stats.coverage_percent:>7.1f}%   "
                    f"{missing_lines}"
                )
            else:
                lines.append(
                    f"{path:<40} {stats.total_branches:>10} "
                    f"{stats.covered_branches:>10} {stats.coverage_percent:>9.1f}%"
                )

                if self.config.verbose and self.config.show_missing:
                    for branch_cov in stats.uncovered_branches:
                        lines.append(
                            f"  - {branch_cov.branch.branch_id}: "
                            f"{branch_cov.branch.description}"
                        )

        if self.config.show_missing_inline:
            lines.append("-" * 90)
        else:
            lines.append("-" * 70)
        lines.append(
            f"{'TOTAL':<40} {summary.total_branches:>10} "
            f"{summary.covered_branches:>10} {summary.coverage_percent:>9.1f}%"
        )
        lines.append("")

        if self.config.fail_under > 0:
            if summary.coverage_percent < self.config.fail_under:
                lines.append(
                    f"FAIL: Coverage {summary.coverage_percent:.1f}% "
                    f"< required {self.config.fail_under:.1f}%"
                )
            else:
                lines.append(
                    f"OK: Coverage {summary.coverage_percent:.1f}% "
                    f">= required {self.config.fail_under:.1f}%"
                )
            lines.append("")

        result = "\n".join(lines)
        if output:
            output.write(result)
        return result

    def _get_missing_lines(self, stats: TemplateCoverageStats) -> str:
        """Get a compact string of missing line numbers.

        Args:
            stats: The template coverage stats.

        Returns:
            Comma-separated line numbers, e.g., "10, 16, 30"
        """
        if not stats.uncovered_branches:
            return ""

        # Get unique line numbers, sorted
        missing = sorted({bc.branch.line for bc in stats.uncovered_branches})
        return ", ".join(str(line) for line in missing)

    def _truncate_path(self, path: str, max_len: int) -> str:
        """Truncate a path to fit in a column.

        Args:
            path: The path to truncate.
            max_len: Maximum length.

        Returns:
            Truncated path with ellipsis if needed.
        """
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3) :]


class JSONReporter:
    """JSON coverage reporter.

    Outputs coverage information in a machine-readable JSON format.
    """

    def __init__(self, config: ReportConfig | None = None) -> None:
        """Initialize the JSON reporter.

        Args:
            config: Optional report configuration.
        """
        self.config = config or ReportConfig()

    def report(
        self,
        summary: CoverageSummary,
        output: TextIO | None = None,
    ) -> str:
        """Generate a JSON coverage report.

        Args:
            summary: The coverage summary to report.
            output: Optional file-like object to write to.

        Returns:
            The JSON string.
        """
        data = {
            "summary": {
                "total_branches": summary.total_branches,
                "covered_branches": summary.covered_branches,
                "coverage_percent": round(summary.coverage_percent, 2),
                "template_count": summary.template_count,
            },
            "templates": [self._template_to_dict(stats) for stats in summary.templates],
        }

        if self.config.fail_under > 0:
            data["fail_under"] = self.config.fail_under
            data["passed"] = summary.coverage_percent >= self.config.fail_under

        result = json.dumps(data, indent=2)
        if output:
            output.write(result)
        return result

    def write_to_file(self, summary: CoverageSummary, path: Path) -> None:
        """Write JSON report to a file.

        Args:
            summary: The coverage summary.
            path: The output file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            self.report(summary, f)

    def _template_to_dict(self, stats: TemplateCoverageStats) -> dict:
        """Convert template stats to a dictionary.

        Args:
            stats: The template coverage stats.

        Returns:
            Dictionary representation.
        """
        data = {
            "path": stats.template_path,
            "total_branches": stats.total_branches,
            "covered_branches": stats.covered_branches,
            "coverage_percent": round(stats.coverage_percent, 2),
        }

        if self.config.show_missing:
            data["uncovered"] = [
                {
                    "branch_id": bc.branch.branch_id,
                    "line": bc.branch.line,
                    "type": bc.branch.branch_type,
                    "description": bc.branch.description,
                }
                for bc in stats.uncovered_branches
            ]
            data["covered"] = [
                {
                    "branch_id": bc.branch.branch_id,
                    "line": bc.branch.line,
                    "type": bc.branch.branch_type,
                    "hit_count": bc.hit_count,
                }
                for bc in stats.covered_branch_list
            ]

        return data


class HTMLReporter:
    """HTML coverage reporter.

    Generates an HTML report with source highlighting.
    """

    def __init__(self, config: ReportConfig | None = None) -> None:
        """Initialize the HTML reporter.

        Args:
            config: Optional report configuration.
        """
        self.config = config or ReportConfig()

    def report(
        self,
        summary: CoverageSummary,
        output_dir: Path,
        sources: dict[str, str] | None = None,
    ) -> None:
        """Generate an HTML coverage report.

        Args:
            summary: The coverage summary.
            output_dir: Directory to write HTML files to.
            sources: Optional dict mapping template paths to source code.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        index_html = self._generate_index(summary)
        (output_dir / "index.html").write_text(index_html)

        if sources:
            for stats in summary.templates:
                if stats.template_path and stats.template_path in sources:
                    template_html = self._generate_template_page(
                        stats, sources[stats.template_path]
                    )
                    safe_name = self._safe_filename(stats.template_path)
                    (output_dir / f"{safe_name}.html").write_text(template_html)

        css = self._generate_css()
        (output_dir / "style.css").write_text(css)

    def _generate_index(self, summary: CoverageSummary) -> str:
        """Generate the index HTML page.

        Args:
            summary: The coverage summary.

        Returns:
            HTML string.
        """
        rows = []
        for stats in sorted(summary.templates, key=lambda s: s.template_path or ""):
            path = stats.template_path or "<string>"
            safe_name = self._safe_filename(stats.template_path or "string")
            coverage_class = self._coverage_class(stats.coverage_percent)
            rows.append(
                ROW_HTML.format(
                    coverage_class=coverage_class,
                    safe_name=safe_name,
                    path=self._escape(path),
                    total_branches=stats.total_branches,
                    covered_branches=stats.covered_branches,
                    coverage_percent=stats.coverage_percent,
                )
            )

        coverage_class = self._coverage_class(summary.coverage_percent)

        return INDEX_HTML.format(
            coverage_class=coverage_class,
            coverage_percent=summary.coverage_percent,
            template_count=summary.template_count,
            covered_branches=summary.covered_branches,
            total_branches=summary.total_branches,
            rows="".join(rows),
        )

    def _generate_template_page(
        self,
        stats: TemplateCoverageStats,
        source: str,
    ) -> str:
        """Generate an HTML page for a single template.

        Args:
            stats: The template coverage stats.
            source: The template source code.

        Returns:
            HTML string.
        """
        covered_lines: set[int] = set()
        uncovered_lines: set[int] = set()

        for bc in stats.covered_branch_list:
            covered_lines.add(bc.branch.line)
        for bc in stats.uncovered_branches:
            uncovered_lines.add(bc.branch.line)

        lines = source.split("\n")
        source_lines = []
        for i, line in enumerate(lines, start=1):
            if i in uncovered_lines:
                line_class = "uncovered"
            elif i in covered_lines:
                line_class = "covered"
            else:
                line_class = ""

            escaped = self._escape(line) or "&nbsp;"
            source_lines.append(
                SOURCE_LINE_HTML.format(
                    line_class=line_class,
                    lineno=i,
                    source=escaped,
                )
            )

        path = stats.template_path or "<string>"
        coverage_class = self._coverage_class(stats.coverage_percent)

        uncovered_items = [
            f"<li>Line {bc.branch.line}: {self._escape(bc.branch.description)}</li>"
            for bc in stats.uncovered_branches
        ]
        uncovered_list = "".join(uncovered_items) or "<li>All branches covered!</li>"

        return TEMPLATE_PAGE_HTML.format(
            path=self._escape(path),
            coverage_class=coverage_class,
            coverage_percent=stats.coverage_percent,
            covered_branches=stats.covered_branches,
            total_branches=stats.total_branches,
            uncovered_list=uncovered_list,
            source_lines="".join(source_lines),
        )

    def _generate_css(self) -> str:
        """Generate CSS stylesheet.

        Returns:
            CSS string.
        """
        return STYLE_CSS

    def _coverage_class(self, percent: float) -> str:
        """Get CSS class based on coverage percentage.

        Args:
            percent: Coverage percentage.

        Returns:
            CSS class name.
        """
        if percent >= 80:
            return "high"
        elif percent >= 50:
            return "medium"
        return "low"

    def _safe_filename(self, path: str | None) -> str:
        """Convert a path to a safe filename.

        Args:
            path: The path.

        Returns:
            Safe filename.
        """
        if not path:
            return "string"
        safe = path.replace("/", "_").replace("\\", "_").replace(":", "_")
        safe = safe.replace(" ", "_").replace(".", "_")
        return safe

    def _escape(self, text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape.

        Returns:
            Escaped text.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


class CoverageReporter:
    """Unified reporter that can output multiple formats.

    Example:
        >>> reporter = CoverageReporter(config)
        >>> reporter.terminal_report(summary)
        >>> reporter.json_report(summary, Path("coverage.json"))
        >>> reporter.html_report(summary, Path("htmlcov"), sources)
    """

    def __init__(self, config: ReportConfig | None = None) -> None:
        """Initialize the coverage reporter.

        Args:
            config: Optional report configuration.
        """
        self.config = config or ReportConfig()
        self._terminal = TerminalReporter(self.config)
        self._json = JSONReporter(self.config)
        self._html = HTMLReporter(self.config)

    def terminal_report(
        self,
        summary: CoverageSummary,
        output: TextIO | None = None,
    ) -> str:
        """Generate a terminal report.

        Args:
            summary: The coverage summary.
            output: Optional output stream.

        Returns:
            The report string.
        """
        return self._terminal.report(summary, output)

    def json_report(
        self,
        summary: CoverageSummary,
        path: Path,
    ) -> None:
        """Write a JSON report to a file.

        Args:
            summary: The coverage summary.
            path: Output file path.
        """
        self._json.write_to_file(summary, path)

    def html_report(
        self,
        summary: CoverageSummary,
        output_dir: Path,
        sources: dict[str, str] | None = None,
    ) -> None:
        """Generate an HTML report.

        Args:
            summary: The coverage summary.
            output_dir: Output directory.
            sources: Optional dict mapping paths to sources.
        """
        self._html.report(summary, output_dir, sources)
