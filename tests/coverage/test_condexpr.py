"""Tests for CondExpr (ternary expression) coverage tracking."""

from jinja2 import Environment

from jinjatest.coverage.discovery import BranchDiscovery
from jinjatest.coverage.environment import CoverageEnvironment
from jinjatest.coverage.transformer import CondExprTransformer
from jinjatest.instrumentation import TestInstrumentation


class TestCondExprDiscovery:
    """Tests for CondExpr branch discovery."""

    def test_simple_ternary(self) -> None:
        """Test discovery of simple ternary expression."""
        discovery = BranchDiscovery()
        result = discovery.discover("{{ a if b else c }}")

        assert "ternary_1_true" in result.branch_ids
        assert "ternary_1_false" in result.branch_ids
        assert result.branch_count == 2

    def test_nested_ternary(self) -> None:
        """Test discovery of nested ternary expressions."""
        discovery = BranchDiscovery()
        result = discovery.discover("{{ a if x else (b if y else c) }}")

        # Should find 2 ternaries = 4 branches
        assert result.branch_count == 4
        assert "ternary_1_true" in result.branch_ids
        assert "ternary_1_false" in result.branch_ids
        assert "ternary_2_true" in result.branch_ids
        assert "ternary_2_false" in result.branch_ids

    def test_ternary_in_set(self) -> None:
        """Test discovery of ternary in set statement."""
        discovery = BranchDiscovery()
        result = discovery.discover("{% set x = a if b else c %}")

        assert result.branch_count == 2
        assert "ternary_1_true" in result.branch_ids
        assert "ternary_1_false" in result.branch_ids

    def test_multiple_ternaries(self) -> None:
        """Test discovery of multiple ternary expressions."""
        discovery = BranchDiscovery()
        result = discovery.discover("{{ a if x else b }} {{ c if y else d }}")

        assert result.branch_count == 4
        assert "ternary_1_true" in result.branch_ids
        assert "ternary_1_false" in result.branch_ids
        assert "ternary_2_true" in result.branch_ids
        assert "ternary_2_false" in result.branch_ids

    def test_ternary_branch_types(self) -> None:
        """Test that ternary branches have correct types."""
        discovery = BranchDiscovery()
        result = discovery.discover("{{ a if b else c }}")

        true_branch = result.get_branch("ternary_1_true")
        false_branch = result.get_branch("ternary_1_false")

        assert true_branch is not None
        assert true_branch.branch_type == "cond_true"

        assert false_branch is not None
        assert false_branch.branch_type == "cond_false"

    def test_ternary_with_if_statement(self) -> None:
        """Test discovery of ternary inside if statement."""
        discovery = BranchDiscovery()
        source = """{% if show %}
{{ a if x else b }}
{% endif %}"""
        result = discovery.discover(source)

        # Should have if branches + ternary branches
        assert "if_1_true" in result.branch_ids
        assert "if_1_false" in result.branch_ids
        assert "ternary_1_true" in result.branch_ids
        assert "ternary_1_false" in result.branch_ids

    def test_chained_ternary(self) -> None:
        """Test discovery of chained ternary (parsed as nested)."""
        discovery = BranchDiscovery()
        # a if x else b if y else c parses as: a if x else (b if y else c)
        result = discovery.discover("{{ a if x else b if y else c }}")

        assert result.branch_count == 4


class TestCondExprTransformer:
    """Tests for CondExpr AST transformation."""

    def test_transforms_condexpr(self) -> None:
        """Test that transformer counts CondExpr nodes."""
        env = Environment()
        ast = env.parse("{{ a if b else c }}")

        transformer = CondExprTransformer()
        transformer.visit(ast)

        assert transformer.count == 1
        assert len(transformer.instrumented) == 1
        assert transformer.instrumented[0]["id"] == "ternary_1"

    def test_transforms_nested_condexpr(self) -> None:
        """Test transformation of nested ternary expressions."""
        env = Environment()
        ast = env.parse("{{ a if x else (b if y else c) }}")

        transformer = CondExprTransformer()
        transformer.visit(ast)

        assert transformer.count == 2
        assert len(transformer.instrumented) == 2

    def test_records_line_numbers(self) -> None:
        """Test that transformer records line numbers."""
        env = Environment()
        ast = env.parse("{{ a if b else c }}")

        transformer = CondExprTransformer()
        transformer.visit(ast)

        assert transformer.instrumented[0]["line"] == 1

    def test_preserves_condexpr_structure(self) -> None:
        """Test that transformer preserves CondExpr (doesn't replace with Call)."""
        from jinja2 import nodes

        env = Environment()
        ast = env.parse("{{ a if b else c }}")

        transformer = CondExprTransformer()
        result = transformer.visit(ast)

        # Find the Output node's child - should still be a CondExpr
        list(result.find_all(nodes.Output))[0]
        # The first node in output should be a CondExpr (wrapped branches)
        assert len(list(result.find_all(nodes.CondExpr))) == 1


class TestCoverageEnvironment:
    """Tests for CoverageEnvironment."""

    def test_preserves_semantics_true_branch(self) -> None:
        """Test that transformed template returns correct value for true branch."""
        env = CoverageEnvironment()
        # Mock trace function that just returns the value
        env.globals["_trace_branch"] = lambda bid, value: value

        template = env.from_string("{{ 'yes' if show else 'no' }}")

        assert template.render(show=True) == "yes"

    def test_preserves_semantics_false_branch(self) -> None:
        """Test that transformed template returns correct value for false branch."""
        env = CoverageEnvironment()
        env.globals["_trace_branch"] = lambda bid, value: value

        template = env.from_string("{{ 'yes' if show else 'no' }}")

        assert template.render(show=False) == "no"

    def test_handles_nested_ternary(self) -> None:
        """Test that nested ternaries work correctly."""
        env = CoverageEnvironment()
        env.globals["_trace_branch"] = lambda bid, value: value

        template = env.from_string("{{ a if x else (b if y else c) }}")

        assert template.render(x=True, a="A", b="B", c="C", y=True) == "A"
        assert template.render(x=False, a="A", b="B", c="C", y=True) == "B"
        assert template.render(x=False, a="A", b="B", c="C", y=False) == "C"

    def test_handles_none_expr2(self) -> None:
        """Test ternary with empty string as else."""
        env = CoverageEnvironment()
        env.globals["_trace_branch"] = lambda bid, value: value

        template = env.from_string("{{ value if show else '' }}")
        assert template.render(show=True, value="hello") == "hello"
        assert template.render(show=False, value="hello") == ""


class TestTraceBranch:
    """Tests for trace_branch recording with TestInstrumentation."""

    def test_records_branch_and_returns_value(self) -> None:
        """Test that trace_branch records and returns value unchanged."""
        instrumentation = TestInstrumentation()

        result = instrumentation.trace_branch("ternary_1_true", "hello")

        assert result == "hello"
        assert "ternary_1_true" in instrumentation.trace_events

    def test_respects_enabled_flag(self) -> None:
        """Test that tracing respects enabled flag."""
        instrumentation = TestInstrumentation()
        instrumentation._enabled = False

        result = instrumentation.trace_branch("ternary_1_true", "hello")

        assert result == "hello"
        assert len(instrumentation.trace_events) == 0

    def test_preserves_various_types(self) -> None:
        """Test that trace_branch preserves various value types."""
        instrumentation = TestInstrumentation()

        # String
        assert instrumentation.trace_branch("t1", "hello") == "hello"

        # Integer
        assert instrumentation.trace_branch("t2", 42) == 42

        # List
        assert instrumentation.trace_branch("t3", [1, 2, 3]) == [1, 2, 3]

        # None
        assert instrumentation.trace_branch("t4", None) is None

        # Dict
        assert instrumentation.trace_branch("t5", {"a": 1}) == {"a": 1}


class TestLazyEvaluation:
    """Tests verifying that lazy evaluation is preserved."""

    def test_nested_ternary_lazy_evaluation(self) -> None:
        """Test that inner ternary is NOT evaluated when outer is true.

        This is the key test that verifies the lazy evaluation fix.
        When x=True, only the true branch should be evaluated,
        and the inner ternary in the false branch should NOT execute.
        """
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        template = env.from_string("{{ a if x else (b if y else c) }}")

        # x=True: only outer true branch is evaluated
        # Inner ternary should NOT be evaluated at all
        result = template.render(x=True, a="A", b="B", c="C", y=True)
        assert result == "A"
        assert "ternary_1_true" in instrumentation.trace_events
        # Inner ternary (ternary_2) should NOT be traced
        assert "ternary_2_true" not in instrumentation.trace_events
        assert "ternary_2_false" not in instrumentation.trace_events

        instrumentation.clear()

        # x=False, y=True: outer false, then inner true
        result = template.render(x=False, a="A", b="B", c="C", y=True)
        assert result == "B"
        assert "ternary_1_false" in instrumentation.trace_events
        assert "ternary_2_true" in instrumentation.trace_events

        instrumentation.clear()

        # x=False, y=False: outer false, then inner false
        result = template.render(x=False, a="A", b="B", c="C", y=False)
        assert result == "C"
        assert "ternary_1_false" in instrumentation.trace_events
        assert "ternary_2_false" in instrumentation.trace_events

    def test_side_effects_only_in_taken_branch(self) -> None:
        """Test that side effects only occur in the taken branch."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        # Track which variables were accessed
        accessed: list[str] = []

        class TrackingValue:
            def __init__(self, name: str, value: str):
                self.name = name
                self.value = value

            def __str__(self) -> str:
                accessed.append(self.name)
                return self.value

        template = env.from_string("{{ a if x else b }}")

        a_val = TrackingValue("a", "A")
        b_val = TrackingValue("b", "B")

        # When x=True, only 'a' should be accessed
        accessed.clear()
        result = template.render(x=True, a=a_val, b=b_val)
        assert result == "A"
        assert "a" in accessed
        assert "b" not in accessed

        # When x=False, only 'b' should be accessed
        accessed.clear()
        result = template.render(x=False, a=a_val, b=b_val)
        assert result == "B"
        assert "b" in accessed
        assert "a" not in accessed


class TestCondExprIntegration:
    """Integration tests for CondExpr with CoverageEnvironment and instrumentation."""

    def test_full_integration(self) -> None:
        """Test full integration of environment, transformer, and instrumentation."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        template = env.from_string("{{ 'yes' if show else 'no' }}")

        # Render with true condition
        result = template.render(show=True)
        assert result == "yes"
        assert "ternary_1_true" in instrumentation.trace_events

        instrumentation.clear()

        # Render with false condition
        result = template.render(show=False)
        assert result == "no"
        assert "ternary_1_false" in instrumentation.trace_events

    def test_multiple_ternaries_integration(self) -> None:
        """Test multiple ternaries in one template."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        template = env.from_string("{{ a if x else b }}-{{ c if y else d }}")

        result = template.render(x=True, a="A", b="B", y=False, c="C", d="D")
        assert result == "A-D"
        assert "ternary_1_true" in instrumentation.trace_events
        assert "ternary_2_false" in instrumentation.trace_events

    def test_ternary_in_filter(self) -> None:
        """Test ternary expression inside a filter."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        template = env.from_string("{{ ('yes' if show else 'no') | upper }}")

        result = template.render(show=True)
        assert result == "YES"
        assert "ternary_1_true" in instrumentation.trace_events

    def test_ternary_with_complex_expressions(self) -> None:
        """Test ternary with complex expressions."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        template = env.from_string("{{ (a + b) if (x > 0) else (c * d) }}")

        result = template.render(a=1, b=2, c=3, d=4, x=5)
        assert result == "3"  # 1 + 2
        assert "ternary_1_true" in instrumentation.trace_events

        instrumentation.clear()

        result = template.render(a=1, b=2, c=3, d=4, x=-1)
        assert result == "12"  # 3 * 4
        assert "ternary_1_false" in instrumentation.trace_events

    def test_deeply_nested_ternaries(self) -> None:
        """Test deeply nested ternaries with lazy evaluation."""
        env = CoverageEnvironment()
        instrumentation = TestInstrumentation()
        env.globals["_trace_branch"] = instrumentation.trace_branch

        # a if x else (b if y else (c if z else d))
        template = env.from_string("{{ a if x else (b if y else (c if z else d)) }}")

        # x=True: only ternary_1_true should be traced
        result = template.render(x=True, a="A", b="B", c="C", d="D", y=True, z=True)
        assert result == "A"
        assert instrumentation.trace_events == ["ternary_1_true"]

        instrumentation.clear()

        # x=False, y=True: ternary_1_false, ternary_2_true
        result = template.render(x=False, a="A", b="B", c="C", d="D", y=True, z=True)
        assert result == "B"
        assert "ternary_1_false" in instrumentation.trace_events
        assert "ternary_2_true" in instrumentation.trace_events
        assert "ternary_3_true" not in instrumentation.trace_events

        instrumentation.clear()

        # x=False, y=False, z=False: all false branches
        result = template.render(x=False, a="A", b="B", c="C", d="D", y=False, z=False)
        assert result == "D"
        assert "ternary_1_false" in instrumentation.trace_events
        assert "ternary_2_false" in instrumentation.trace_events
        assert "ternary_3_false" in instrumentation.trace_events
