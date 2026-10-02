"""Coverage-instrumenting Jinja2 Environment.

This module provides a custom Environment subclass that instruments
templates for CondExpr coverage tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment

if TYPE_CHECKING:
    from jinja2 import nodes


class CoverageEnvironment(Environment):
    """Jinja2 Environment that instruments templates for coverage tracking.

    Overrides _generate() to transform CondExpr nodes before Python code
    generation, enabling branch coverage tracking without source manipulation.
    """

    def _generate(
        self,
        source: nodes.Template,
        name: str | None,
        filename: str | None,
        defer_init: bool = False,
    ) -> str:
        """Generate Python code with CondExpr instrumentation.

        Args:
            source: The parsed template AST.
            name: Optional template name.
            filename: Optional filename for debugging.
            defer_init: Whether to defer initialization.

        Returns:
            Generated Python code string.
        """
        from jinja2 import nodes as n

        from jinjatest.coverage.transformer import CondExprTransformer

        if list(source.find_all(n.CondExpr)):
            transformer = CondExprTransformer(event_prefix=_event_prefix(name))
            source = transformer.visit(source)

        return super()._generate(source, name, filename, defer_init)


def _event_prefix(name: str | None) -> str:
    """Get the trace event prefix for a compiled template.

    Templates compiled under a loader name (i.e., loaded through a loader
    rather than from a string) emit namespaced events so their branch hits
    can be routed to the tracker registered under that name. Templates
    compiled without a name (the TemplateSpec root) emit bare ids.

    Args:
        name: The template name passed to compilation, or None.

    Returns:
        "<name>::" when coverage is enabled and name is set, else "".
    """
    if name is None:
        return ""
    try:
        from jinjatest.coverage.collector import get_coverage_collector

        if get_coverage_collector().enabled:
            return f"{name}::"
    except ImportError:
        # Coverage module is optional
        pass
    return ""
