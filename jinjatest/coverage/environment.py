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

        # Only transform if there are CondExpr nodes
        if list(source.find_all(n.CondExpr)):
            transformer = CondExprTransformer()
            source = transformer.visit(source)

        return super()._generate(source, name, filename, defer_init)
