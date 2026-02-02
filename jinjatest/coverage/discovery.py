"""
Branch discovery for Jinja templates.

This module provides functionality to walk the Jinja2 AST and discover
all conditional branches that can be tracked for coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from jinja2 import Environment

if TYPE_CHECKING:
    from jinja2 import nodes


@dataclass
class BranchInfo:
    """Information about a single branch in a template."""

    branch_id: str
    branch_type: str
    line: int
    description: str
    has_else: bool = False

    def __hash__(self) -> int:
        return hash(self.branch_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BranchInfo):
            return NotImplemented
        return self.branch_id == other.branch_id


@dataclass
class DiscoveryResult:
    """Result of branch discovery for a template."""

    branches: list[BranchInfo] = field(default_factory=list)
    template_path: str | None = None

    @property
    def branch_ids(self) -> set[str]:
        """Get set of all branch IDs."""
        return {b.branch_id for b in self.branches}

    @property
    def branch_count(self) -> int:
        """Get total number of branches."""
        return len(self.branches)

    def get_branch(self, branch_id: str) -> BranchInfo | None:
        """Get branch info by ID."""
        for branch in self.branches:
            if branch.branch_id == branch_id:
                return branch
        return None


class BranchDiscovery:
    """Discovers conditional branches in Jinja templates by walking the AST.

    Handles the following node types:
    - If: Generates if_<line>_true and if_<line>_false branches
    - For: Generates for_<line>_body and for_<line>_else branches
    - Macro: Generates macro_<name> branches (for tracking if macro was called)
    - Include: Generates include_<line> branches

    For elif chains, the AST represents them as nested If nodes,
    so we handle them recursively.
    """

    def __init__(self, env: Environment | None = None) -> None:
        """Initialize the branch discovery.

        Args:
            env: Optional Jinja environment to use for parsing.
                 If not provided, a default environment is created.
        """
        self._env = env or Environment()
        self._condexpr_count = 0  # Counter for unique CondExpr IDs

    def discover(
        self, source: str, template_path: str | None = None
    ) -> DiscoveryResult:
        """Discover all branches in a template source.

        Args:
            source: The template source code.
            template_path: Optional path for identification in reports.

        Returns:
            DiscoveryResult containing all discovered branches.
        """
        self._condexpr_count = 0  # Reset counter for each discovery
        ast = self._env.parse(source)
        branches: list[BranchInfo] = []
        self._walk_node(ast, branches)

        return DiscoveryResult(branches=branches, template_path=template_path)

    def _walk_node(
        self,
        node: nodes.Node,
        branches: list[BranchInfo],
        in_elif: bool = False,
    ) -> None:
        """Recursively walk AST nodes to find branches.

        Args:
            node: The current AST node.
            branches: List to append discovered branches to.
            in_elif: Whether we're processing an elif chain.
        """
        from jinja2 import nodes

        if isinstance(node, nodes.If):
            self._handle_if_node(node, branches, in_elif)
        elif isinstance(node, nodes.For):
            self._handle_for_node(node, branches)
        elif isinstance(node, nodes.Macro):
            self._handle_macro_node(node, branches)
        elif isinstance(node, nodes.Include):
            self._handle_include_node(node, branches)
        elif isinstance(node, nodes.CondExpr):
            self._handle_condexpr_node(node, branches)
        else:
            for child in node.iter_child_nodes():
                self._walk_node(child, branches)

    def _handle_if_node(
        self,
        node: nodes.If,
        branches: list[BranchInfo],
        in_elif: bool = False,
        parent_has_else: bool = False,
    ) -> None:
        """Handle If node (includes elif handling).

        Args:
            node: The If AST node.
            branches: List to append discovered branches to.
            in_elif: Whether this If is part of an elif chain.
            parent_has_else: Whether the parent if/elif has an else clause.
        """
        from jinja2 import nodes

        line = node.lineno
        prefix = "elif" if in_elif else "if"

        branches.append(
            BranchInfo(
                branch_id=f"{prefix}_{line}_true",
                branch_type=f"{prefix}_true",
                line=line,
                description=f"{prefix} condition at line {line} is true",
            )
        )

        # Check if there are elif branches
        # In Jinja AST, elif_ contains If nodes for each elif clause
        has_elif = bool(node.elif_)
        has_else = bool(node.else_)

        if has_elif:
            # Process elif chain - the elif_ contains If nodes
            # Pass along whether there's an else clause at the end
            for i, elif_node in enumerate(node.elif_):
                if isinstance(elif_node, nodes.If):
                    is_last = i == len(node.elif_) - 1
                    # The else_ of this node applies to the last elif
                    self._handle_if_node(
                        elif_node,
                        branches,
                        in_elif=True,
                        parent_has_else=has_else if is_last else False,
                    )

        # Add false branch based on the structure
        if in_elif:
            # For elif nodes, the parent handles the false branch
            # We only need to add it if we're the last elif AND parent has else
            if parent_has_else:
                branches.append(
                    BranchInfo(
                        branch_id=f"{prefix}_{line}_false",
                        branch_type=f"{prefix}_false",
                        line=line,
                        description=f"{prefix} condition at line {line} is false (else taken)",
                        has_else=True,
                    )
                )
            elif not has_elif:
                # Last elif in chain with no else - implicit false
                branches.append(
                    BranchInfo(
                        branch_id=f"{prefix}_{line}_false",
                        branch_type=f"{prefix}_false",
                        line=line,
                        description=f"{prefix} condition at line {line} is false (no else)",
                        has_else=False,
                    )
                )
        else:
            # For top-level if
            if has_else and not has_elif:
                # Plain else branch (no elif)
                branches.append(
                    BranchInfo(
                        branch_id=f"{prefix}_{line}_false",
                        branch_type=f"{prefix}_false",
                        line=line,
                        description=f"{prefix} condition at line {line} is false (else taken)",
                        has_else=True,
                    )
                )
            elif not has_else and not has_elif:
                # No else or elif branch - implicit false case
                branches.append(
                    BranchInfo(
                        branch_id=f"{prefix}_{line}_false",
                        branch_type=f"{prefix}_false",
                        line=line,
                        description=f"{prefix} condition at line {line} is false (no else)",
                        has_else=False,
                    )
                )
            # If has_elif, the false branch is handled by the last elif

        for child in node.body:
            self._walk_node(child, branches)

        for child in node.else_:
            self._walk_node(child, branches)

    def _handle_for_node(
        self,
        node: nodes.For,
        branches: list[BranchInfo],
    ) -> None:
        """Handle For node.

        Args:
            node: The For AST node.
            branches: List to append discovered branches to.
        """
        line = node.lineno

        branches.append(
            BranchInfo(
                branch_id=f"for_{line}_body",
                branch_type="for_body",
                line=line,
                description=f"for loop at line {line} has items",
            )
        )

        if node.else_:
            branches.append(
                BranchInfo(
                    branch_id=f"for_{line}_else",
                    branch_type="for_else",
                    line=line,
                    description=f"for loop at line {line} has no items (else taken)",
                    has_else=True,
                )
            )
        else:
            # No else block - implicit else case (nothing happens when empty)
            branches.append(
                BranchInfo(
                    branch_id=f"for_{line}_else",
                    branch_type="for_else",
                    line=line,
                    description=f"for loop at line {line} has no items (no else)",
                    has_else=False,
                )
            )

        for child in node.body:
            self._walk_node(child, branches)

        for child in node.else_:
            self._walk_node(child, branches)

    def _handle_macro_node(
        self,
        node: nodes.Macro,
        branches: list[BranchInfo],
    ) -> None:
        """Handle Macro node.

        Args:
            node: The Macro AST node.
            branches: List to append discovered branches to.
        """
        # Track macro definition (not calls - those are harder to track)
        branches.append(
            BranchInfo(
                branch_id=f"macro_{node.name}",
                branch_type="macro",
                line=node.lineno,
                description=f"macro '{node.name}' defined at line {node.lineno}",
            )
        )

        for child in node.body:
            self._walk_node(child, branches)

    def _handle_include_node(
        self,
        node: nodes.Include,
        branches: list[BranchInfo],
    ) -> None:
        """Handle Include node.

        Args:
            node: The Include AST node.
            branches: List to append discovered branches to.
        """
        from jinja2 import nodes

        template_name = "dynamic"
        if isinstance(node.template, nodes.Const):
            template_name = str(node.template.value)

        branches.append(
            BranchInfo(
                branch_id=f"include_{node.lineno}_{template_name}",
                branch_type="include",
                line=node.lineno,
                description=f"include '{template_name}' at line {node.lineno}",
            )
        )

    def _handle_condexpr_node(
        self,
        node: nodes.CondExpr,
        branches: list[BranchInfo],
    ) -> None:
        """Handle CondExpr (ternary) node.

        Args:
            node: The CondExpr AST node.
            branches: List to append discovered branches to.
        """
        from jinja2 import nodes

        self._condexpr_count += 1
        branch_id = f"ternary_{self._condexpr_count}"
        line = node.lineno

        branches.append(
            BranchInfo(
                branch_id=f"{branch_id}_true",
                branch_type="cond_true",
                line=line,
                description=f"ternary at line {line} condition is true",
            )
        )

        branches.append(
            BranchInfo(
                branch_id=f"{branch_id}_false",
                branch_type="cond_false",
                line=line,
                description=f"ternary at line {line} condition is false",
            )
        )

        # Recursively handle nested CondExpr in test, expr1, and expr2
        for child in node.iter_child_nodes():
            if isinstance(child, nodes.CondExpr):
                self._handle_condexpr_node(child, branches)
            else:
                self._walk_node(child, branches)
