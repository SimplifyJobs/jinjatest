"""Tests for branch discovery."""

from jinjatest.coverage.discovery import BranchDiscovery, BranchInfo, DiscoveryResult


class TestBranchInfo:
    """Tests for BranchInfo dataclass."""

    def test_branch_info_creation(self) -> None:
        """Test creating a BranchInfo."""
        info = BranchInfo(
            branch_id="if_1_true",
            branch_type="if_true",
            line=1,
            description="if condition at line 1 is true",
        )
        assert info.branch_id == "if_1_true"
        assert info.branch_type == "if_true"
        assert info.line == 1

    def test_branch_info_hash(self) -> None:
        """Test BranchInfo is hashable."""
        info1 = BranchInfo("if_1_true", "if_true", 1, "desc")
        info2 = BranchInfo("if_1_true", "if_true", 1, "desc")
        assert hash(info1) == hash(info2)

    def test_branch_info_equality(self) -> None:
        """Test BranchInfo equality based on branch_id."""
        info1 = BranchInfo("if_1_true", "if_true", 1, "desc1")
        info2 = BranchInfo("if_1_true", "if_false", 2, "desc2")
        assert info1 == info2  # Same branch_id

    def test_branch_info_not_equal_to_other_types(self) -> None:
        """Test BranchInfo not equal to other types."""
        info = BranchInfo("if_1_true", "if_true", 1, "desc")
        assert info != "if_1_true"
        assert info != 42

    def test_branch_info_has_else_default(self) -> None:
        """Test BranchInfo has_else defaults to False."""
        info = BranchInfo("if_1_false", "if_false", 1, "desc")
        assert info.has_else is False

    def test_branch_info_has_else_explicit(self) -> None:
        """Test BranchInfo has_else can be set explicitly."""
        info = BranchInfo("if_1_false", "if_false", 1, "desc", has_else=True)
        assert info.has_else is True


class TestDiscoveryResult:
    """Tests for DiscoveryResult dataclass."""

    def test_empty_result(self) -> None:
        """Test empty discovery result."""
        result = DiscoveryResult()
        assert result.branches == []
        assert result.branch_ids == set()
        assert result.branch_count == 0

    def test_result_with_branches(self) -> None:
        """Test discovery result with branches."""
        branches = [
            BranchInfo("if_1_true", "if_true", 1, "desc"),
            BranchInfo("if_1_false", "if_false", 1, "desc"),
        ]
        result = DiscoveryResult(branches=branches, template_path="test.j2")

        assert result.branch_count == 2
        assert result.branch_ids == {"if_1_true", "if_1_false"}
        assert result.template_path == "test.j2"

    def test_get_branch(self) -> None:
        """Test getting a branch by ID."""
        branches = [
            BranchInfo("if_1_true", "if_true", 1, "desc"),
            BranchInfo("if_1_false", "if_false", 1, "desc"),
        ]
        result = DiscoveryResult(branches=branches)

        branch = result.get_branch("if_1_true")
        assert branch is not None
        assert branch.branch_id == "if_1_true"

    def test_get_branch_not_found(self) -> None:
        """Test getting a non-existent branch."""
        result = DiscoveryResult()
        assert result.get_branch("nonexistent") is None


class TestBranchDiscovery:
    """Tests for BranchDiscovery class."""

    def test_discover_empty_template(self) -> None:
        """Test discovery on empty template."""
        discovery = BranchDiscovery()
        result = discovery.discover("")

        assert result.branch_count == 0

    def test_discover_simple_if(self) -> None:
        """Test discovery of simple if statement."""
        discovery = BranchDiscovery()
        source = """{% if show_header %}
Header content
{% endif %}"""
        result = discovery.discover(source)

        assert result.branch_count == 2
        assert "if_1_true" in result.branch_ids
        assert "if_1_false" in result.branch_ids

    def test_discover_if_else(self) -> None:
        """Test discovery of if-else statement."""
        discovery = BranchDiscovery()
        source = """{% if show_header %}
Header
{% else %}
No header
{% endif %}"""
        result = discovery.discover(source)

        assert result.branch_count == 2
        assert "if_1_true" in result.branch_ids
        assert "if_1_false" in result.branch_ids

    def test_discover_elif_chain(self) -> None:
        """Test discovery of elif chain."""
        discovery = BranchDiscovery()
        source = """{% if level == 1 %}
Level 1
{% elif level == 2 %}
Level 2
{% elif level == 3 %}
Level 3
{% else %}
Other
{% endif %}"""
        result = discovery.discover(source)

        # Should have if_true, elif_true, elif_true, and elif_false
        assert "if_1_true" in result.branch_ids
        # elif branches are nested
        assert any("elif" in bid for bid in result.branch_ids)

    def test_discover_for_loop(self) -> None:
        """Test discovery of for loop."""
        discovery = BranchDiscovery()
        source = """{% for item in items %}
{{ item }}
{% endfor %}"""
        result = discovery.discover(source)

        assert "for_1_body" in result.branch_ids

    def test_discover_for_loop_with_else(self) -> None:
        """Test discovery of for loop with else."""
        discovery = BranchDiscovery()
        source = """{% for item in items %}
{{ item }}
{% else %}
No items
{% endfor %}"""
        result = discovery.discover(source)

        assert "for_1_body" in result.branch_ids
        assert "for_1_else" in result.branch_ids

    def test_discover_nested_conditions(self) -> None:
        """Test discovery of nested conditions."""
        discovery = BranchDiscovery()
        source = """{% if outer %}
{% if inner %}
Inner content
{% endif %}
{% endif %}"""
        result = discovery.discover(source)

        # Should have branches for both if statements
        assert "if_1_true" in result.branch_ids
        assert "if_1_false" in result.branch_ids
        assert "if_2_true" in result.branch_ids
        assert "if_2_false" in result.branch_ids

    def test_discover_macro(self) -> None:
        """Test discovery of macro definition."""
        discovery = BranchDiscovery()
        source = """{% macro greet(name) %}
Hello, {{ name }}!
{% endmacro %}"""
        result = discovery.discover(source)

        assert "macro_greet" in result.branch_ids

    def test_discover_include(self) -> None:
        """Test discovery of include statement."""
        discovery = BranchDiscovery()
        source = """{% include "header.j2" %}
Content
{% include "footer.j2" %}"""
        result = discovery.discover(source)

        # Should have includes
        assert any("include" in bid for bid in result.branch_ids)
        assert any("header" in bid for bid in result.branch_ids)
        assert any("footer" in bid for bid in result.branch_ids)

    def test_discover_with_template_path(self) -> None:
        """Test discovery records template path."""
        discovery = BranchDiscovery()
        source = "{% if x %}y{% endif %}"
        result = discovery.discover(source, template_path="test.j2")

        assert result.template_path == "test.j2"

    def test_discover_complex_template(self) -> None:
        """Test discovery on complex template."""
        discovery = BranchDiscovery()
        source = """{% if user.is_admin %}
Admin panel
{% else %}
{% for item in menu_items %}
<li>{{ item }}</li>
{% else %}
No menu items
{% endfor %}
{% endif %}

{% macro render_item(item) %}
{% if item.active %}
<strong>{{ item.name }}</strong>
{% else %}
{{ item.name }}
{% endif %}
{% endmacro %}"""
        result = discovery.discover(source)

        # Should discover multiple branches
        assert result.branch_count >= 6

    def test_discover_bare_if_has_else_false(self) -> None:
        """Test that bare if statements have has_else=False."""
        discovery = BranchDiscovery()
        source = """{% if show %}
Content
{% endif %}"""
        result = discovery.discover(source)

        false_branch = result.get_branch("if_1_false")
        assert false_branch is not None
        assert false_branch.has_else is False

    def test_discover_if_with_else_has_else_true(self) -> None:
        """Test that if statements with else have has_else=True."""
        discovery = BranchDiscovery()
        source = """{% if show %}
Content
{% else %}
Other
{% endif %}"""
        result = discovery.discover(source)

        false_branch = result.get_branch("if_1_false")
        assert false_branch is not None
        assert false_branch.has_else is True

    def test_discover_elif_chain_without_else(self) -> None:
        """Test elif chain without final else has has_else=False."""
        discovery = BranchDiscovery()
        source = """{% if level == 1 %}
Level 1
{% elif level == 2 %}
Level 2
{% endif %}"""
        result = discovery.discover(source)

        # Last elif should have has_else=False
        elif_false = result.get_branch("elif_3_false")
        assert elif_false is not None
        assert elif_false.has_else is False

    def test_discover_elif_chain_with_else(self) -> None:
        """Test elif chain with final else has has_else=True."""
        discovery = BranchDiscovery()
        source = """{% if level == 1 %}
Level 1
{% elif level == 2 %}
Level 2
{% else %}
Other
{% endif %}"""
        result = discovery.discover(source)

        # Last elif should have has_else=True
        elif_false = result.get_branch("elif_3_false")
        assert elif_false is not None
        assert elif_false.has_else is True

    def test_discover_nested_ifs_has_else(self) -> None:
        """Test nested ifs track has_else correctly."""
        discovery = BranchDiscovery()
        source = """{% if outer %}
{% if inner %}
Content
{% else %}
Inner else
{% endif %}
{% endif %}"""
        result = discovery.discover(source)

        # Outer if has no else
        outer_false = result.get_branch("if_1_false")
        assert outer_false is not None
        assert outer_false.has_else is False

        # Inner if has else
        inner_false = result.get_branch("if_2_false")
        assert inner_false is not None
        assert inner_false.has_else is True

    def test_discover_bare_for_has_else_false(self) -> None:
        """Test that bare for loops have has_else=False on else branch."""
        discovery = BranchDiscovery()
        source = """{% for item in items %}
{{ item }}
{% endfor %}"""
        result = discovery.discover(source)

        # Should have body and else branches
        assert "for_1_body" in result.branch_ids
        assert "for_1_else" in result.branch_ids

        else_branch = result.get_branch("for_1_else")
        assert else_branch is not None
        assert else_branch.has_else is False

    def test_discover_for_with_else_has_else_true(self) -> None:
        """Test that for loops with else have has_else=True."""
        discovery = BranchDiscovery()
        source = """{% for item in items %}
{{ item }}
{% else %}
No items
{% endfor %}"""
        result = discovery.discover(source)

        else_branch = result.get_branch("for_1_else")
        assert else_branch is not None
        assert else_branch.has_else is True
