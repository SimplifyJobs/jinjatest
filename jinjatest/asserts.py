"""
Assertion helpers for pytest-friendly testing.

Provides assertion methods that raise AssertionError with helpful diffs.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jinjatest.rendered import RenderedPrompt


class PromptAssertionError(AssertionError):
    """Raised when a prompt assertion fails."""

    pass


def _diff_strings(expected: str, actual: str, context_lines: int = 3) -> str:
    """Generate a unified diff between two strings."""
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)

    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile="expected",
        tofile="actual",
        n=context_lines,
    )

    return "".join(diff)


def _truncate(s: str, max_len: int = 200) -> str:
    """Truncate string for display."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


class PromptAsserts:
    """Assertion helpers for RenderedPrompt objects.

    Provides chainable assertion methods that raise AssertionError with
    helpful messages when assertions fail.

    Example:
        a = PromptAsserts(rendered)
        a.contains("Hello").not_contains("Error").regex(r"\\d+ items")
    """

    def __init__(
        self, rendered: RenderedPrompt, *, use_normalized: bool = False
    ) -> None:
        """Initialize with a rendered prompt.

        Args:
            rendered: The RenderedPrompt to assert on.
            use_normalized: If True, use normalized text for all assertions.
        """
        self._rendered = rendered
        self._use_normalized = use_normalized

    @property
    def text(self) -> str:
        """Get the text being asserted on."""
        if self._use_normalized:
            return self._rendered.normalized
        return self._rendered.clean_text

    def normalized(self) -> PromptAsserts:
        """Return a new PromptAsserts that uses normalized text.

        Returns:
            A new PromptAsserts instance using normalized text.
        """
        return PromptAsserts(self._rendered, use_normalized=True)

    def contains(self, substring: str) -> PromptAsserts:
        """Assert that the text contains the given substring.

        Args:
            substring: The substring to search for.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If substring is not found.
        """
        if substring not in self.text:
            raise PromptAssertionError(
                f"Expected text to contain: {_truncate(repr(substring))}\n"
                f"But it was not found in:\n{_truncate(self.text, 500)}"
            )
        return self

    def not_contains(self, substring: str) -> PromptAsserts:
        """Assert that the text does not contain the given substring.

        Args:
            substring: The substring that should not be present.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If substring is found.
        """
        if substring in self.text:
            # Find position for better error message
            pos = self.text.find(substring)
            context_start = max(0, pos - 30)
            context_end = min(len(self.text), pos + len(substring) + 30)
            context = self.text[context_start:context_end]

            raise PromptAssertionError(
                f"Expected text to NOT contain: {_truncate(repr(substring))}\n"
                f"But it was found at position {pos}:\n...{context}..."
            )
        return self

    def contains_line(self, expected_line: str) -> PromptAsserts:
        """Assert that some line contains the expected text.

        Args:
            expected_line: Text that should appear in at least one line.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If no line contains the text.
        """
        lines = self.text.split("\n")
        if not any(expected_line in line for line in lines):
            raise PromptAssertionError(
                f"Expected some line to contain: {_truncate(repr(expected_line))}\n"
                f"Lines searched ({len(lines)}):\n"
                + "\n".join(
                    f"  {i}: {_truncate(line, 80)}" for i, line in enumerate(lines[:10])
                )
                + ("\n  ..." if len(lines) > 10 else "")
            )
        return self

    def has_exact_line(self, expected_line: str) -> PromptAsserts:
        """Assert that an exact line exists.

        Args:
            expected_line: The exact line that should exist.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If the exact line doesn't exist.
        """
        lines = self.text.split("\n")
        if expected_line not in lines:
            # Find closest match for better error message
            close_matches = difflib.get_close_matches(
                expected_line, lines, n=3, cutoff=0.5
            )
            hint = ""
            if close_matches:
                hint = "\n\nDid you mean one of these?\n" + "\n".join(
                    f"  - {_truncate(m, 80)}" for m in close_matches
                )

            raise PromptAssertionError(
                f"Expected exact line: {_truncate(repr(expected_line))}\n"
                f"But it was not found.{hint}"
            )
        return self

    def regex(self, pattern: str, flags: int = 0) -> PromptAsserts:
        """Assert that the text matches a regex pattern.

        Args:
            pattern: The regex pattern to match.
            flags: Regex flags (e.g., re.IGNORECASE).

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If pattern doesn't match.
        """
        if not re.search(pattern, self.text, flags):
            raise PromptAssertionError(
                f"Expected text to match pattern: {pattern}\n"
                f"But no match was found in:\n{_truncate(self.text, 500)}"
            )
        return self

    def not_regex(self, pattern: str, flags: int = 0) -> PromptAsserts:
        """Assert that the text does not match a regex pattern.

        Args:
            pattern: The regex pattern that should not match.
            flags: Regex flags (e.g., re.IGNORECASE).

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If pattern matches.
        """
        match = re.search(pattern, self.text, flags)
        if match:
            raise PromptAssertionError(
                f"Expected text to NOT match pattern: {pattern}\n"
                f"But found match at position {match.start()}: {_truncate(repr(match.group()), 100)}"
            )
        return self

    def line_count(self, expected: int) -> PromptAsserts:
        """Assert the number of lines.

        Args:
            expected: The expected number of lines.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If line count doesn't match.
        """
        actual = len(self.text.split("\n"))
        if actual != expected:
            raise PromptAssertionError(f"Expected {expected} lines, but found {actual}")
        return self

    def line_count_between(self, min_lines: int, max_lines: int) -> PromptAsserts:
        """Assert the line count is within a range.

        Args:
            min_lines: Minimum number of lines (inclusive).
            max_lines: Maximum number of lines (inclusive).

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If line count is outside range.
        """
        actual = len(self.text.split("\n"))
        if not (min_lines <= actual <= max_lines):
            raise PromptAssertionError(
                f"Expected between {min_lines} and {max_lines} lines, but found {actual}"
            )
        return self

    def equals(self, expected: str) -> PromptAsserts:
        """Assert exact equality.

        Args:
            expected: The expected text.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If texts don't match.
        """
        if self.text != expected:
            diff = _diff_strings(expected, self.text)
            raise PromptAssertionError(f"Text does not match expected:\n{diff}")
        return self

    def equals_json(self, expected: Any) -> PromptAsserts:
        """Assert that parsed JSON equals expected value.

        Args:
            expected: The expected JSON-serializable value.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If JSON doesn't match.
        """
        actual = self._rendered.as_json()
        if actual != expected:
            expected_str = json.dumps(expected, indent=2, sort_keys=True)
            actual_str = json.dumps(actual, indent=2, sort_keys=True)
            diff = _diff_strings(expected_str, actual_str)
            raise PromptAssertionError(f"JSON does not match expected:\n{diff}")
        return self

    def has_trace(self, event: str) -> PromptAsserts:
        """Assert that a trace event was recorded.

        Args:
            event: The trace event to check for.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If event not found.
        """
        if not self._rendered.has_trace(event):
            events = ", ".join(repr(e) for e in self._rendered.trace_events) or "(none)"
            raise PromptAssertionError(
                f"Expected trace event: {repr(event)}\nRecorded events: {events}"
            )
        return self

    def not_has_trace(self, event: str) -> PromptAsserts:
        """Assert that a trace event was not recorded.

        Args:
            event: The trace event that should not be present.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If event is found.
        """
        if self._rendered.has_trace(event):
            count = self._rendered.trace_count(event)
            raise PromptAssertionError(
                f"Expected trace event NOT to be recorded: {repr(event)}\n"
                f"But it was recorded {count} time(s)"
            )
        return self

    def snapshot(
        self,
        name: str,
        *,
        snapshot_dir: str | Path = "tests/__snapshots__",
        update: bool = False,
    ) -> PromptAsserts:
        """Assert against a snapshot file.

        Args:
            name: The snapshot name (used as filename).
            snapshot_dir: Directory for snapshot files.
            update: If True, update the snapshot instead of comparing.

        Returns:
            Self for chaining.

        Raises:
            PromptAssertionError: If snapshot doesn't match.
        """
        snapshot_path = Path(snapshot_dir) / f"{name}.txt"

        if update or not snapshot_path.exists():
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(self.text)
            return self

        expected = snapshot_path.read_text()
        if self.text != expected:
            diff = _diff_strings(expected, self.text)
            raise PromptAssertionError(
                f"Snapshot mismatch for '{name}':\n{diff}\n\n"
                f"Run with update=True to update the snapshot."
            )
        return self


def assert_no_undefined(text: str) -> None:
    """Assert that rendered text has no Jinja undefined markers.

    Checks for common patterns that indicate undefined variables:
    - {{ variable }}
    - Undefined

    Args:
        text: The rendered text to check.

    Raises:
        PromptAssertionError: If undefined markers are found.
    """
    # Check for literal "Undefined" which Jinja produces for undefined vars
    if "Undefined" in text:
        raise PromptAssertionError(
            "Found 'Undefined' in rendered text - possible undefined variable.\n"
            f"Text: {_truncate(text, 500)}"
        )

    # Check for unreplaced template syntax (shouldn't happen with StrictUndefined)
    pattern = r"\{\{\s*\w+\s*\}\}"
    matches = re.findall(pattern, text)
    if matches:
        raise PromptAssertionError(
            f"Found unreplaced template syntax: {matches[:5]}\n"
            f"Text: {_truncate(text, 500)}"
        )
