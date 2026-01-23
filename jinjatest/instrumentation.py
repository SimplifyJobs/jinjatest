"""
Instrumentation helpers for test-only anchors and traces.

These helpers allow templates to emit markers that tests can use to:
- Select specific sections of rendered output
- Track which code branches were executed during rendering
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Sentinel markers for anchors (using ASCII record separator character)
ANCHOR_START = "\x1e"
ANCHOR_END = "\x1e"
ANCHOR_PATTERN = re.compile(rf"{ANCHOR_START}ANCHOR:([^{ANCHOR_END}]+){ANCHOR_END}")


@dataclass
class TraceRecorder:
    """Records trace events during template rendering."""

    events: list[str] = field(default_factory=list)

    def record(self, event: str) -> None:
        """Record a trace event."""
        self.events.append(event)

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()


@dataclass
class AnchorIndex:
    """Index of anchor positions in rendered text."""

    anchors: dict[str, tuple[int, int]] = field(default_factory=dict)
    clean_text: str = ""

    @classmethod
    def from_text(cls, text: str) -> AnchorIndex:
        """Parse anchor markers from text and build an index.

        Returns an AnchorIndex with:
        - anchors: mapping of anchor name to (start, end) positions in clean_text
        - clean_text: the text with all anchor markers removed
        """
        anchors: dict[str, tuple[int, int]] = {}
        positions: list[tuple[str, int]] = []

        # Find all anchor markers and their positions
        clean_parts: list[str] = []
        last_end = 0

        for match in ANCHOR_PATTERN.finditer(text):
            anchor_name = match.group(1)
            # Add text before this marker
            clean_parts.append(text[last_end : match.start()])
            # Record position in clean text
            clean_pos = sum(len(p) for p in clean_parts)
            positions.append((anchor_name, clean_pos))
            last_end = match.end()

        # Add remaining text
        clean_parts.append(text[last_end:])
        clean_text = "".join(clean_parts)

        # Build anchor ranges: each anchor extends from its position to the next anchor or end
        for i, (name, start) in enumerate(positions):
            if i + 1 < len(positions):
                end = positions[i + 1][1]
            else:
                end = len(clean_text)
            anchors[name] = (start, end)

        return cls(anchors=anchors, clean_text=clean_text)

    def get_section(self, name: str) -> str | None:
        """Get the text content for a named anchor section."""
        if name not in self.anchors:
            return None
        start, end = self.anchors[name]
        return self.clean_text[start:end]

    def has_anchor(self, name: str) -> bool:
        """Check if an anchor exists."""
        return name in self.anchors

    def list_anchors(self) -> list[str]:
        """List all anchor names in order of appearance."""
        return list(self.anchors.keys())


class TestInstrumentation:
    """Instrumentation context for test mode.

    Provides `anchor` and `trace` functions that emit markers/record events.
    """

    def __init__(self) -> None:
        self._trace_recorder = TraceRecorder()
        self._enabled = True

    @property
    def trace_events(self) -> list[str]:
        """Get list of recorded trace events."""
        return self._trace_recorder.events.copy()

    def anchor(self, name: str) -> str:
        """Emit an anchor marker.

        In test mode: returns a sentinel marker that can be indexed.
        """
        if self._enabled:
            return f"{ANCHOR_START}ANCHOR:{name}{ANCHOR_END}"
        return ""

    def trace(self, event: str) -> str:
        """Record a trace event.

        In test mode: appends to the trace recorder and returns empty string.
        """
        if self._enabled:
            self._trace_recorder.record(event)
        return ""

    def clear(self) -> None:
        """Clear all trace events."""
        self._trace_recorder.clear()


class ProductionInstrumentation:
    """Instrumentation context for production mode.

    All methods return empty strings (no-ops).
    """

    @property
    def trace_events(self) -> list[str]:
        """No trace events in production mode."""
        return []

    def anchor(self, name: str) -> str:
        """No-op in production mode."""
        return ""

    def trace(self, event: str) -> str:
        """No-op in production mode."""
        return ""

    def clear(self) -> None:
        """No-op in production mode."""
        pass


def create_instrumentation(
    test_mode: bool = True,
) -> TestInstrumentation | ProductionInstrumentation:
    """Create an instrumentation context.

    Args:
        test_mode: If True, create TestInstrumentation that emits markers.
                  If False, create ProductionInstrumentation (no-ops).
    """
    if test_mode:
        return TestInstrumentation()
    return ProductionInstrumentation()
