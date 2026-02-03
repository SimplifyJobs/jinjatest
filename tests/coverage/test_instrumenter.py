"""Tests for auto-instrumenter."""

from jinjatest.coverage.instrumenter import AutoInstrumenter, InstrumentationResult


class TestInstrumentationResult:
    """Tests for InstrumentationResult dataclass."""

    def test_was_modified_true(self) -> None:
        """Test was_modified returns True when source changed."""
        result = InstrumentationResult(
            source="modified",
            original_source="original",
            discovery=None,
            insertions=1,
        )
        assert result.was_modified is True

    def test_was_modified_false(self) -> None:
        """Test was_modified returns False when source unchanged."""
        result = InstrumentationResult(
            source="same",
            original_source="same",
            discovery=None,
            insertions=0,
        )
        assert result.was_modified is False


class TestAutoInstrumenter:
    """Tests for AutoInstrumenter class."""

    def test_instrument_empty_template(self) -> None:
        """Test instrumenting empty template."""
        instrumenter = AutoInstrumenter()
        result = instrumenter.instrument("")

        assert result.source == ""
        assert result.insertions == 0

    def test_instrument_no_branches(self) -> None:
        """Test instrumenting template with no branches."""
        instrumenter = AutoInstrumenter()
        source = "Hello, {{ name }}!"
        result = instrumenter.instrument(source)

        assert result.source == source
        assert result.insertions == 0

    def test_instrument_simple_if(self) -> None:
        """Test instrumenting simple if statement."""
        instrumenter = AutoInstrumenter()
        source = """{% if show %}
Content
{% endif %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("if_1_true") }}' in result.source
        assert result.insertions >= 1

    def test_instrument_if_else(self) -> None:
        """Test instrumenting if-else statement."""
        instrumenter = AutoInstrumenter()
        source = """{% if show %}
Yes
{% else %}
No
{% endif %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("if_1_true") }}' in result.source
        # else branch should also have trace
        assert result.insertions >= 2

    def test_instrument_elif(self) -> None:
        """Test instrumenting elif statement."""
        instrumenter = AutoInstrumenter()
        source = """{% if level == 1 %}
One
{% elif level == 2 %}
Two
{% else %}
Other
{% endif %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("if_1_true") }}' in result.source
        assert 'jt.trace("elif_' in result.source

    def test_instrument_for_loop(self) -> None:
        """Test instrumenting for loop."""
        instrumenter = AutoInstrumenter()
        source = """{% for item in items %}
{{ item }}
{% endfor %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("for_1_body") }}' in result.source
        assert result.insertions >= 1

    def test_instrument_macro(self) -> None:
        """Test instrumenting macro definition."""
        instrumenter = AutoInstrumenter()
        source = """{% macro greet(name) %}
Hello, {{ name }}!
{% endmacro %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("macro_greet") }}' in result.source
        assert result.insertions >= 1

    def test_instrument_preserves_whitespace_control(self) -> None:
        """Test that whitespace control characters are preserved."""
        instrumenter = AutoInstrumenter()
        source = """{%- if show -%}
Content
{%- endif -%}"""
        result = instrumenter.instrument(source)

        # Should still work with whitespace control
        assert 'jt.trace("if_1_true")' in result.source

    def test_instrument_nested_conditions(self) -> None:
        """Test instrumenting nested conditions."""
        instrumenter = AutoInstrumenter()
        source = """{% if outer %}
{% if inner %}
Content
{% endif %}
{% endif %}"""
        result = instrumenter.instrument(source)

        assert '{{ jt.trace("if_1_true") }}' in result.source
        assert '{{ jt.trace("if_2_true") }}' in result.source

    def test_instrument_template_path(self) -> None:
        """Test template path is recorded."""
        instrumenter = AutoInstrumenter()
        source = "{% if x %}y{% endif %}"
        result = instrumenter.instrument(source, template_path="test.j2")

        assert result.discovery.template_path == "test.j2"

    def test_instrument_complex_template(self) -> None:
        """Test instrumenting complex template."""
        instrumenter = AutoInstrumenter()
        source = """{% if user.is_authenticated %}
Welcome, {{ user.name }}!
{% if user.is_admin %}
<a href="/admin">Admin Panel</a>
{% endif %}
{% for notification in notifications %}
<div class="notification">{{ notification.message }}</div>
{% else %}
<div>No notifications</div>
{% endfor %}
{% else %}
<a href="/login">Please log in</a>
{% endif %}"""
        result = instrumenter.instrument(source)

        # Should have multiple insertions
        assert result.insertions >= 4
        # Discovery should match
        assert result.discovery.branch_count >= 4

    def test_instrument_idempotent_discovery(self) -> None:
        """Test that discovery is consistent with instrumentation."""
        instrumenter = AutoInstrumenter()
        source = """{% if a %}
{% for b in items %}
{{ b }}
{% endfor %}
{% endif %}"""
        result = instrumenter.instrument(source)

        # Number of discovered branches should match what we instrument
        discovered_branches = result.discovery.branch_ids

        # Check that traces for discovered branches exist
        for branch_id in discovered_branches:
            if "true" in branch_id or "body" in branch_id:
                # These should have traces inserted
                assert branch_id in result.source or "jt.trace" in result.source


class TestImplicitFalseInstrumentation:
    """Tests for implicit false branch instrumentation."""

    def test_bare_if_gets_implicit_false(self) -> None:
        """Test bare if statement gets implicit false trace injected."""
        instrumenter = AutoInstrumenter()
        source = "{% if x %}content{% endif %}"
        result = instrumenter.instrument(source)

        # Should inject else with trace before endif
        assert '{% else %}{{ jt.trace("if_1_false") }}{% endif %}' in result.source

    def test_if_with_else_no_injection(self) -> None:
        """Test if with else does not get implicit false injection."""
        instrumenter = AutoInstrumenter()
        source = """{% if x %}
content
{% else %}
other
{% endif %}"""
        result = instrumenter.instrument(source)

        # Should not have double else
        assert result.source.count("{% else %}") == 1
        # The else trace should be handled by normal else instrumentation
        assert '{{ jt.trace("if_1_false") }}' in result.source

    def test_nested_ifs_implicit_false(self) -> None:
        """Test nested ifs get correct implicit false injection."""
        instrumenter = AutoInstrumenter()
        source = """{% if outer %}
{% if inner %}
content
{% endif %}
{% endif %}"""
        result = instrumenter.instrument(source)

        # Both should get implicit false traces
        assert '{% else %}{{ jt.trace("if_1_false") }}{% endif %}' in result.source
        assert '{% else %}{{ jt.trace("if_2_false") }}{% endif %}' in result.source

    def test_nested_inner_has_else_outer_doesnt(self) -> None:
        """Test nested if where inner has else but outer doesn't."""
        instrumenter = AutoInstrumenter()
        source = """{% if outer %}
{% if inner %}
content
{% else %}
inner else
{% endif %}
{% endif %}"""
        result = instrumenter.instrument(source)

        # Outer should get implicit false
        assert '{% else %}{{ jt.trace("if_1_false") }}{% endif %}' in result.source
        # Inner should NOT get implicit false (has else)
        assert "if_2_false" in result.source  # From normal else instrumentation
        # Count elses - should have 2: inner's original + outer's injected
        assert result.source.count("{% else %}") == 2

    def test_elif_chain_without_else(self) -> None:
        """Test elif chain without final else gets implicit false."""
        instrumenter = AutoInstrumenter()
        source = """{% if level == 1 %}
One
{% elif level == 2 %}
Two
{% endif %}"""
        result = instrumenter.instrument(source)

        # Last elif should get implicit false
        assert "elif_3_false" in result.source
        assert '{% else %}{{ jt.trace("elif_3_false") }}{% endif %}' in result.source

    def test_elif_chain_with_else_no_injection(self) -> None:
        """Test elif chain with else does not get extra injection."""
        instrumenter = AutoInstrumenter()
        source = """{% if level == 1 %}
One
{% elif level == 2 %}
Two
{% else %}
Other
{% endif %}"""
        result = instrumenter.instrument(source)

        # Should have normal else trace, not injected
        assert result.source.count("{% else %}") == 1
        # elif false should be traced via normal else handling
        assert "elif_3_false" in result.source

    def test_whitespace_control_preserved(self) -> None:
        """Test whitespace control characters work with implicit false."""
        instrumenter = AutoInstrumenter()
        source = """{%- if x -%}
content
{%- endif -%}"""
        result = instrumenter.instrument(source)

        # Should inject before endif
        assert "if_1_false" in result.source
        assert "{% else %}" in result.source

    def test_single_line_if(self) -> None:
        """Test single line if gets implicit false injection."""
        instrumenter = AutoInstrumenter()
        source = "prefix{% if x %}content{% endif %}suffix"
        result = instrumenter.instrument(source)

        # Should inject between content and endif
        assert '{% else %}{{ jt.trace("if_1_false") }}{% endif %}' in result.source
        assert "prefix" in result.source
        assert "suffix" in result.source

    def test_multiple_bare_ifs_on_different_lines(self) -> None:
        """Test multiple bare ifs each get implicit false."""
        instrumenter = AutoInstrumenter()
        source = """{% if a %}A{% endif %}
{% if b %}B{% endif %}"""
        result = instrumenter.instrument(source)

        assert "if_1_false" in result.source
        assert "if_2_false" in result.source
        # Both should have injected elses
        assert result.source.count("{% else %}") == 2

    def test_complex_nesting(self) -> None:
        """Test complex nesting with mixed else/no-else."""
        instrumenter = AutoInstrumenter()
        source = """{% if a %}
  {% if b %}B{% endif %}
  {% if c %}C{% else %}not C{% endif %}
{% endif %}"""
        result = instrumenter.instrument(source)

        # 'a' is bare - should get injection
        assert "if_1_false" in result.source
        # 'b' is bare - should get injection
        assert "if_2_false" in result.source
        # 'c' has else - should NOT get injection, but should have trace
        assert "if_3_false" in result.source
        # Count injected elses: a + b = 2, plus c's original = 3
        assert result.source.count("{% else %}") == 3

    def test_bare_for_gets_implicit_else(self) -> None:
        """Test bare for loop gets implicit else trace injected."""
        instrumenter = AutoInstrumenter()
        source = "{% for item in items %}{{ item }}{% endfor %}"
        result = instrumenter.instrument(source)

        # Should inject else with trace before endfor
        assert '{% else %}{{ jt.trace("for_1_else") }}{% endfor %}' in result.source

    def test_for_with_else_no_injection(self) -> None:
        """Test for with else does not get implicit else injection."""
        instrumenter = AutoInstrumenter()
        source = """{% for item in items %}
{{ item }}
{% else %}
No items
{% endfor %}"""
        result = instrumenter.instrument(source)

        # Should not have double else
        assert result.source.count("{% else %}") == 1
        # The else trace should be handled by normal else instrumentation
        assert '{{ jt.trace("for_1_else") }}' in result.source

    def test_nested_for_implicit_else(self) -> None:
        """Test nested for loops get correct implicit else injection."""
        instrumenter = AutoInstrumenter()
        source = """{% for outer in outers %}
{% for inner in inners %}
{{ inner }}
{% endfor %}
{% endfor %}"""
        result = instrumenter.instrument(source)

        # Both should get implicit else traces
        assert "for_1_else" in result.source
        assert "for_2_else" in result.source
        # Both should have injected elses
        assert result.source.count("{% else %}") == 2

    def test_for_inside_if_implicit(self) -> None:
        """Test for inside bare if both get implicit branches."""
        instrumenter = AutoInstrumenter()
        source = """{% if show %}
{% for item in items %}{{ item }}{% endfor %}
{% endif %}"""
        result = instrumenter.instrument(source)

        # Both if and for should have implicit branches
        assert "if_1_false" in result.source
        assert "for_2_else" in result.source
