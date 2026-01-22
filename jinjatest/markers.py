"""
Comment-based markers for Jinja templates.

This module provides functionality to transform Jinja comment markers into
instrumentation function calls, enabling jinjatest to be a dev-only dependency.

Marker syntax:
    {#jt:anchor:<name>#}  - Section anchor marker
    {#jt:trace:<name>#}   - Trace event marker

Where <name> must be a valid Python identifier: [a-zA-Z_][a-zA-Z0-9_]*
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from jinja2 import Environment, Template

    from jinjatest.instrumentation import TestInstrumentation

# Regex patterns for comment markers
# Name must be a valid Python identifier
ANCHOR_PATTERN = re.compile(r"\{#jt:anchor:([a-zA-Z_][a-zA-Z0-9_]*)#\}")
TRACE_PATTERN = re.compile(r"\{#jt:trace:([a-zA-Z_][a-zA-Z0-9_]*)#\}")


class MarkerTransform(NamedTuple):
    """Result of transforming a template source."""

    source: str
    anchor_names: list[str]
    trace_names: list[str]


@dataclass
class TemplateMarkers:
    """Information about markers in a template."""

    anchors: list[str]
    traces: list[str]

    @property
    def has_markers(self) -> bool:
        """Check if any markers were found."""
        return bool(self.anchors or self.traces)


def transform_markers(source: str) -> MarkerTransform:
    """
    Transform comment-based markers into jt function calls.

    Args:
        source: Raw template source with comment markers

    Returns:
        MarkerTransform with transformed source and discovered marker names

    Example:
        >>> result = transform_markers("{#jt:anchor:intro#}\\nHello")
        >>> '{{ jt.anchor("intro") }}' in result.source
        True
        >>> result.anchor_names
        ['intro']
    """
    anchor_names: list[str] = []
    trace_names: list[str] = []

    def replace_anchor(match: re.Match[str]) -> str:
        name = match.group(1)
        anchor_names.append(name)
        return '{{ jt.anchor("' + name + '") }}'

    def replace_trace(match: re.Match[str]) -> str:
        name = match.group(1)
        trace_names.append(name)
        return '{{ jt.trace("' + name + '") }}'

    transformed = ANCHOR_PATTERN.sub(replace_anchor, source)
    transformed = TRACE_PATTERN.sub(replace_trace, transformed)

    return MarkerTransform(
        source=transformed,
        anchor_names=anchor_names,
        trace_names=trace_names,
    )


def has_markers(source: str) -> bool:
    """
    Check if source contains any jt comment markers.

    Args:
        source: Template source to check

    Returns:
        True if any markers are found, False otherwise

    Example:
        >>> has_markers("{#jt:anchor:x#}")
        True
        >>> has_markers("regular {# comment #}")
        False
    """
    return bool(ANCHOR_PATTERN.search(source) or TRACE_PATTERN.search(source))


def discover_markers(source: str) -> TemplateMarkers:
    """
    Discover all jt markers in a template without transforming.

    Useful for:
    - Validating marker names
    - Generating documentation
    - CI checks for marker consistency

    Args:
        source: Template source to scan

    Returns:
        TemplateMarkers with lists of anchor and trace names

    Example:
        >>> markers = discover_markers("{#jt:anchor:system#}\\n{#jt:trace:debug#}")
        >>> markers.anchors
        ['system']
        >>> markers.traces
        ['debug']
    """
    anchors = ANCHOR_PATTERN.findall(source)
    traces = TRACE_PATTERN.findall(source)
    return TemplateMarkers(anchors=anchors, traces=traces)


def load_template_with_markers(
    env: Environment,
    template_path: str,
    instrumentation: TestInstrumentation | None = None,
) -> Template:
    """
    Load a template from an environment, transforming comment markers.

    This allows using comment markers with any Jinja environment.

    Args:
        env: The Jinja environment (should already have jt global if instrumentation needed)
        template_path: Path to template (relative to env's loader)
        instrumentation: Optional instrumentation instance for trace capture

    Returns:
        Compiled Template with markers transformed

    Raises:
        ValueError: If the environment has no loader configured

    Example:
        from jinja2 import Environment, FileSystemLoader
        from jinjatest import create_instrumentation
        from jinjatest.markers import load_template_with_markers

        env = Environment(loader=FileSystemLoader("templates/"))
        inst = create_instrumentation(test_mode=True)
        env.globals["jt"] = inst
        template = load_template_with_markers(env, "my_prompt.j2", inst)
        result = template.render({"name": "World"})
    """
    if env.loader is None:
        raise ValueError("Environment must have a loader configured")

    # Get the raw source from the environment's loader
    source, _, _ = env.loader.get_source(env, template_path)

    # Transform markers
    transform_result = transform_markers(source)

    # Compile from transformed source
    return env.from_string(transform_result.source)
