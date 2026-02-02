"""AST transformer for CondExpr instrumentation.

This module provides a NodeTransformer that transforms CondExpr (ternary)
nodes to track branch execution while preserving lazy evaluation semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import nodes
from jinja2.visitor import NodeTransformer

if TYPE_CHECKING:
    pass


class CondExprTransformer(NodeTransformer):
    """Transforms CondExpr nodes to track branch execution.

    Preserves lazy evaluation by keeping the CondExpr structure intact
    and wrapping each branch expression in a trace call.

    Converts:
        {{ value if condition else default }}

    To AST equivalent of:
        {{ _trace_branch('ternary_1_true', value)
           if condition
           else _trace_branch('ternary_1_false', default) }}

    The trace function records which branch was taken and returns
    the value unchanged. Only the taken branch is evaluated.
    """

    def __init__(self) -> None:
        """Initialize the transformer."""
        self.count = 0
        self.instrumented: list[dict[str, str | int]] = []

    def _wrap_with_trace(
        self, expr: nodes.Expr, branch_id: str, lineno: int
    ) -> nodes.Call:
        """Wrap an expression with a trace call.

        Args:
            expr: The expression to wrap.
            branch_id: The branch identifier (e.g., 'ternary_1_true').
            lineno: Line number for the new node.

        Returns:
            A Call node: _trace_branch(branch_id, expr)
        """
        return nodes.Call(
            nodes.Name("_trace_branch", "load"),
            [nodes.Const(branch_id), expr],
            [],  # kwargs
            None,  # dyn_args
            None,  # dyn_kwargs
            lineno=lineno,
        )

    def visit_CondExpr(self, node: nodes.CondExpr) -> nodes.CondExpr:
        """Transform a CondExpr node to track branch execution.

        Preserves the CondExpr structure (maintaining lazy evaluation)
        but wraps expr1 and expr2 with trace calls.

        Args:
            node: The CondExpr AST node to transform.

        Returns:
            A modified CondExpr with traced branches.
        """
        self.count += 1
        branch_id = f"ternary_{self.count}"

        self.instrumented.append(
            {
                "id": branch_id,
                "line": node.lineno,
            }
        )

        # Process children first (handles nested ternaries in expr1/expr2)
        # This must happen AFTER we increment count for correct ordering
        self.generic_visit(node)

        traced_expr1 = self._wrap_with_trace(
            node.expr1, f"{branch_id}_true", node.lineno
        )
        traced_expr2 = self._wrap_with_trace(
            node.expr2 if node.expr2 is not None else nodes.Const(None),
            f"{branch_id}_false",
            node.lineno,
        )

        return nodes.CondExpr(
            node.test,
            traced_expr1,
            traced_expr2,
            lineno=node.lineno,
        )
