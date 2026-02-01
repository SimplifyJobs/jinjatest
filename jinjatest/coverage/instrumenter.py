"""
Auto-instrumenter for Jinja templates.

This module provides functionality to automatically insert trace calls
into Jinja templates based on discovered branches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jinjatest.coverage.discovery import BranchDiscovery, DiscoveryResult


@dataclass
class InstrumentationResult:
    """Result of auto-instrumenting a template."""

    source: str
    original_source: str
    discovery: DiscoveryResult
    insertions: int

    @property
    def was_modified(self) -> bool:
        """Check if the source was modified."""
        return self.source != self.original_source


class AutoInstrumenter:
    """Auto-instruments Jinja templates with trace calls for branch coverage.

    Inserts `{{ jt.trace("branch_id") }}` calls after block tags to track
    which branches are executed during rendering.

    Example:
        >>> instrumenter = AutoInstrumenter()
        >>> result = instrumenter.instrument('''
        ... {% if show_header %}
        ... Header
        ... {% else %}
        ... No header
        ... {% endif %}
        ... ''')
        >>> '{{ jt.trace("if_2_true") }}' in result.source
        True
    """

    IF_PATTERN = re.compile(
        r"(\{%-?\s*if\s+.*?-?%\})",
        re.DOTALL,
    )
    ELIF_PATTERN = re.compile(
        r"(\{%-?\s*elif\s+.*?-?%\})",
        re.DOTALL,
    )
    ELSE_PATTERN = re.compile(
        r"(\{%-?\s*else\s*-?%\})",
        re.DOTALL,
    )
    FOR_PATTERN = re.compile(
        r"(\{%-?\s*for\s+.*?-?%\})",
        re.DOTALL,
    )
    MACRO_PATTERN = re.compile(
        r"(\{%-?\s*macro\s+(\w+)\s*\(.*?\)\s*-?%\})",
        re.DOTALL,
    )

    BLOCK_TAG_PATTERN = re.compile(
        r"\{%-?\s*(if|elif|else|endif|for|endfor)\b.*?-?%\}",
        re.DOTALL,
    )

    def __init__(self) -> None:
        """Initialize the auto-instrumenter."""
        self._discovery = BranchDiscovery()

    def instrument(
        self,
        source: str,
        template_path: str | None = None,
    ) -> InstrumentationResult:
        """Instrument a template source with trace calls.

        Args:
            source: The template source code.
            template_path: Optional path for identification.

        Returns:
            InstrumentationResult containing the instrumented source.
        """
        discovery = self._discovery.discover(source, template_path)

        line_branches: dict[int, list[str]] = {}
        for branch in discovery.branches:
            if branch.line not in line_branches:
                line_branches[branch.line] = []
            line_branches[branch.line].append(branch.branch_id)

        lines = source.split("\n")
        instrumented_lines: list[str] = []
        insertions = 0

        for line_num, line in enumerate(lines, start=1):
            new_line = line

            new_line, count = self._instrument_if(new_line, line_num)
            insertions += count

            new_line, count = self._instrument_elif(new_line, line_num)
            insertions += count

            new_line, count = self._instrument_else(new_line, line_num, discovery)
            insertions += count

            new_line, count = self._instrument_for(new_line, line_num)
            insertions += count

            new_line, count = self._instrument_macro(new_line)
            insertions += count

            instrumented_lines.append(new_line)

        instrumented_source = "\n".join(instrumented_lines)

        instrumented_source, implicit_count = self._instrument_implicit_false(
            instrumented_source, discovery
        )
        insertions += implicit_count

        return InstrumentationResult(
            source=instrumented_source,
            original_source=source,
            discovery=discovery,
            insertions=insertions,
        )

    def _instrument_if(self, line: str, line_num: int) -> tuple[str, int]:
        """Instrument if statements in a line.

        Args:
            line: The line to process.
            line_num: The line number.

        Returns:
            Tuple of (modified line, insertion count).
        """
        count = 0

        def replace_if(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            tag = match.group(1)
            trace_call = f'{{{{ jt.trace("if_{line_num}_true") }}}}'
            return f"{tag}{trace_call}"

        new_line = self.IF_PATTERN.sub(replace_if, line)
        return new_line, count

    def _instrument_elif(self, line: str, line_num: int) -> tuple[str, int]:
        """Instrument elif statements in a line.

        Args:
            line: The line to process.
            line_num: The line number.

        Returns:
            Tuple of (modified line, insertion count).
        """
        count = 0

        def replace_elif(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            tag = match.group(1)
            trace_call = f'{{{{ jt.trace("elif_{line_num}_true") }}}}'
            return f"{tag}{trace_call}"

        new_line = self.ELIF_PATTERN.sub(replace_elif, line)
        return new_line, count

    def _instrument_else(
        self,
        line: str,
        line_num: int,
        discovery: DiscoveryResult,
    ) -> tuple[str, int]:
        """Instrument else statements in a line.

        Args:
            line: The line to process.
            line_num: The line number.
            discovery: The discovery result to find associated if/for.

        Returns:
            Tuple of (modified line, insertion count).
        """
        count = 0

        def replace_else(match: re.Match[str]) -> str:
            nonlocal count

            branch_id = self._find_else_branch_id(line_num, discovery)
            if branch_id:
                count += 1
                tag = match.group(1)
                trace_call = f'{{{{ jt.trace("{branch_id}") }}}}'
                return f"{tag}{trace_call}"

            return match.group(0)

        new_line = self.ELSE_PATTERN.sub(replace_else, line)
        return new_line, count

    def _find_else_branch_id(
        self,
        else_line: int,
        discovery: DiscoveryResult,
    ) -> str | None:
        """Find the branch ID for an else statement.

        This looks for the nearest if/elif/for that would
        have a false/else branch at this line.

        Args:
            else_line: The line number of the else statement.
            discovery: The discovery result.

        Returns:
            The branch ID or None if not found.
        """
        candidates: list[tuple[int, str]] = []
        for branch in discovery.branches:
            if branch.branch_type in ("if_false", "elif_false", "for_else"):
                if branch.has_else and branch.line <= else_line:
                    candidates.append((branch.line, branch.branch_id))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _instrument_for(self, line: str, line_num: int) -> tuple[str, int]:
        """Instrument for loop statements in a line.

        Args:
            line: The line to process.
            line_num: The line number.

        Returns:
            Tuple of (modified line, insertion count).
        """
        count = 0

        def replace_for(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            tag = match.group(1)
            trace_call = f'{{{{ jt.trace("for_{line_num}_body") }}}}'
            return f"{tag}{trace_call}"

        new_line = self.FOR_PATTERN.sub(replace_for, line)
        return new_line, count

    def _instrument_macro(self, line: str) -> tuple[str, int]:
        """Instrument macro definitions in a line.

        Args:
            line: The line to process.

        Returns:
            Tuple of (modified line, insertion count).
        """
        count = 0

        def replace_macro(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            tag = match.group(1)
            macro_name = match.group(2)
            trace_call = f'{{{{ jt.trace("macro_{macro_name}") }}}}'
            return f"{tag}{trace_call}"

        new_line = self.MACRO_PATTERN.sub(replace_macro, line)
        return new_line, count

    def _instrument_implicit_false(
        self,
        source: str,
        discovery: DiscoveryResult,
    ) -> tuple[str, int]:
        """Instrument implicit false/else branches for bare if and for statements.

        For bare if statements like {% if x %}...{% endif %}, we inject
        {% else %}{{ jt.trace("if_X_false") }} before {% endif %}.

        For bare for loops like {% for x in items %}...{% endfor %}, we inject
        {% else %}{{ jt.trace("for_X_else") }} before {% endfor %}.

        Args:
            source: The template source (already line-instrumented).
            discovery: The discovery result containing branch info.

        Returns:
            Tuple of (modified source, insertion count).
        """
        implicit_branches: dict[int, str] = {}
        for branch in discovery.branches:
            if not branch.has_else:
                if branch.branch_type.endswith("_false"):
                    implicit_branches[branch.line] = branch.branch_id
                elif branch.branch_type == "for_else":
                    implicit_branches[branch.line] = branch.branch_id

        if not implicit_branches:
            return source, 0

        # Stack entry: (block_type, start_line, last_branch_line, has_seen_else)
        stack: list[tuple[str, int, int, bool]] = []
        insertions: list[tuple[int, str]] = []

        for match in self.BLOCK_TAG_PATTERN.finditer(source):
            keyword = match.group(1)
            tag_start = match.start()
            line_num = source[:tag_start].count("\n") + 1

            if keyword == "if":
                stack.append(("if", line_num, line_num, False))
            elif keyword == "for":
                stack.append(("for", line_num, line_num, False))
            elif keyword == "elif":
                if stack and stack[-1][0] == "if":
                    block_type, start_line, _, has_else = stack.pop()
                    stack.append((block_type, start_line, line_num, has_else))
            elif keyword == "else":
                if stack:
                    block_type, start_line, last_branch_line, _ = stack.pop()
                    stack.append((block_type, start_line, last_branch_line, True))
            elif keyword == "endif":
                if stack and stack[-1][0] == "if":
                    _, start_line, last_branch_line, has_else = stack.pop()
                    if not has_else and last_branch_line in implicit_branches:
                        branch_id = implicit_branches[last_branch_line]
                        insert_text = f'{{% else %}}{{{{ jt.trace("{branch_id}") }}}}'
                        insertions.append((tag_start, insert_text))
            elif keyword == "endfor":
                if stack and stack[-1][0] == "for":
                    _, start_line, _, has_else = stack.pop()
                    if not has_else and start_line in implicit_branches:
                        branch_id = implicit_branches[start_line]
                        insert_text = f'{{% else %}}{{{{ jt.trace("{branch_id}") }}}}'
                        insertions.append((tag_start, insert_text))

        insertions.sort(key=lambda x: x[0], reverse=True)
        for pos, text in insertions:
            source = source[:pos] + text + source[pos:]

        return source, len(insertions)
