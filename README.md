# jinjatest

A type-safe, structured testing library for Jinja templates.

## Installation

```bash
uv add jinjatest          # or: uv add jinjatest[yaml]
```

## Features

- **Type-safe context validation** with Pydantic
- **Structured output parsing** (JSON, YAML, XML, markdown, fenced code blocks)
- **Test instrumentation** with anchors and traces
- **Pytest integration** with fixtures and snapshots
- **StrictUndefined by default** - missing variables fail loudly
- **Coverage output** - output the test coverage for Jinja2 templates

## Quick Start

### Basic Usage

```python
from pydantic import BaseModel
from jinjatest import TemplateSpec, PromptAsserts

class Ctx(BaseModel):
    user_name: str
    plan: str  # "free" | "pro"

# Load template with context validation
spec = TemplateSpec.from_file("prompts/welcome.j2", context_model=Ctx)

def test_welcome_pro_user():
    rendered = spec.render({"user_name": "Ada", "plan": "pro"})

    a = PromptAsserts(rendered).normalized()
    a.contains("Hello, Ada")
    a.not_contains("Upgrade now")  # pro users shouldn't see this
    a.regex(r"Plan:\s*pro")
```

### Structured Output (JSON)

```jinja2
{% set config = {"model": model_name, "temperature": temperature} %}
{{ config | tojson }}
```

```python
def test_config_output():
    rendered = spec.render({"model_name": "gpt-4", "temperature": 0.7})
    config = rendered.as_json()
    assert config["model"] == "gpt-4"
    assert config["temperature"] == 0.7
```

### Structured Output (XML)

Supports fragments with multiple root elements:

```jinja2
<tool name="search">
<query>{{ query }}</query>
</tool>

{% if include_filter %}
<tool name="filter">
<criteria>{{ criteria }}</criteria>
</tool>
{% endif %}
```

```python
def test_xml_tool_calls():
    rendered = spec.render({"query": "python tutorials", "include_filter": True, "criteria": "beginner"})
    tools = rendered.as_xml()  # Returns list[XMLElement]
    assert tools[0].attrib["name"] == "search"
    assert tools[0].find("query").text == "python tutorials"
    # Use strict=True for single-root XML
```

### Fenced Code Blocks

Extract code blocks from markdown-style output:

```python
def test_fenced_json_blocks():
    rendered = spec.render({"setting_name": "timeout", "setting_value": 30})
    configs = rendered.as_json_blocks()  # Extracts all ```json blocks
    assert configs[0]["value"] == 30
    # Also: as_yaml_blocks(), as_xml_blocks()
```

### Section Testing with Anchors

```jinja2
{#jt:anchor:system#}
System rules: Be helpful, be concise.

{#jt:anchor:user#}
User: {{ user_name }}
Request: {{ request }}

{% if context_items %}
{#jt:anchor:context#}
Context: {% for item in context_items %}- {{ item }}{% endfor %}
{% else %}
{#jt:trace:no_context#}
{% endif %}
```

```python
def test_sections():
    rendered = spec.render({"user_name": "Ada", "request": "Help", "context_items": ["doc1"]})
    assert rendered.section("user").contains("Ada")
    assert rendered.section("system").not_contains("Ada")

def test_branch_coverage():
    rendered = spec.render({"user_name": "Ada", "request": "Help", "context_items": []})
    assert rendered.has_trace("no_context")  # Verify branch was taken
```

### Macros as Functions

```jinja2
{% macro build_prompt(user_input, context=None) %}
You are a helpful assistant.
User: {{ user_input }}
{% if context %}Context: {{ context }}{% endif %}
{% endmacro %}
```

```python
def test_prompt_builder():
    build_prompt = spec.macro("build_prompt")
    assert "User: Hello" in build_prompt("Hello")
    assert "Context: Info" in build_prompt("Hello", context="Info")
```

## API Reference

### TemplateSpec

```python
spec = TemplateSpec.from_file("template.j2", context_model=MyModel)
spec = TemplateSpec.from_string("Hello {{ name }}!", context_model=MyModel)
rendered = spec.render({"name": "World"})
my_macro = spec.macro("macro_name")
```

Options: `template_dir`, `strict_undefined=True`, `test_mode=True`, `use_comment_markers=True`

### RenderedPrompt

**Properties:** `text`, `normalized`, `clean_text`, `lines`, `normalized_lines`, `trace_events`

**Parsing:**
```python
rendered.as_json()                 # Parse as JSON (allow_comments=True for // comments)
rendered.as_yaml()                 # Parse as YAML (requires pyyaml)
rendered.as_xml(strict=False)      # Parse as XML (strict=True for single root)
rendered.as_json_blocks()          # Extract ```json blocks
rendered.as_yaml_blocks()          # Extract ```yaml blocks
rendered.as_xml_blocks()           # Extract ```xml blocks
rendered.as_markdown_sections()    # Parse markdown headings
```

**Sections & Traces:**
```python
rendered.section("name")           # Get section by anchor
rendered.has_section("name")       # Check section exists
rendered.has_trace("event")        # Check trace was recorded
rendered.trace_count("event")      # Count trace occurrences
```

**Query helpers:**
```python
rendered.contains("text")          # Check substring
rendered.not_contains("text")      # Check absence
rendered.matches(r"pattern")       # Regex match
rendered.find_all(r"pattern")      # Find all matches
```

### PromptAsserts

```python
a = PromptAsserts(rendered).normalized()
a.contains("text").not_contains("bad").regex(r"pattern")
a.has_trace("event").snapshot("name")
```

### Instrumentation

```jinja2
{#jt:anchor:section_name#}
{#jt:trace:event_name#}
```

Markers are automatically transformed when `test_mode=True`. Comments render as empty strings in production, so jinjatest can be dev-only.

**Custom Jinja environment:**
```python
env = Environment(loader=FileSystemLoader("templates/"))
env.globals["my_filter"] = lambda x: x.upper()
spec = TemplateSpec.from_file("my_template.j2", env=env)
```

## Pytest Integration

```python
def test_with_fixtures(template_from_string, jinja_env):
    spec = template_from_string("Hello {{ name }}!")
    assert spec.render({"name": "World"}).text == "Hello World!"

def test_with_snapshots(snapshot_manager, template_from_string):
    rendered = template_from_string("Hello {{ name }}!").render({"name": "World"})
    snapshot_manager.compare_or_update("greeting", rendered.text)
```

Update snapshots: `pytest --update-snapshots`

## Advanced Configuration

```python
env = create_environment(
    template_paths=["templates/", "shared/"],
    mock_templates={"header.j2": "Mock Header"},
    filters={"my_filter": lambda x: x.upper()},
    globals={"version": "1.0"},
)
spec = TemplateSpec.from_file("template.j2", env=env)
spec.assert_variables_subset_of({"user_name", "plan", "items"})  # CI guardrails
```

## Template Coverage

jinjatest tracks branch coverage by instrumenting your templates at render time. When you use `TemplateSpec`, it automatically discovers all conditional branches (`if`, `elif`, `else`, `for` loops, macros, etc.) and records which paths are executed during tests. This lets you identify untested template logic without modifying your templates.

```bash
pytest --jt-cov --jt-cov-fail-under=80 --jt-cov-report=term-verbose
```

```
======================================================================
JINJA TEMPLATE COVERAGE
======================================================================

Template                                   Branches    Covered   Coverage
----------------------------------------------------------------------
templates/components/nav.j2                       8          5      62.5%
  - if_3_false: if condition at line 12 is false
  - for_1_empty: for loop at line 18 has no items
  - if_5_true: if condition at line 25 is true
templates/email/confirm.j2                        6          6     100.0%
templates/welcome.j2                              4          3      75.0%
  - elif_1: elif branch at line 8 is taken
----------------------------------------------------------------------
TOTAL                                            18         14      77.8%

FAIL: Coverage 77.8% < required 80.0%
```

| Option | Description |
|--------|-------------|
| `--jt-cov` | Enable template coverage |
| `--jt-cov-fail-under=N` | Fail if coverage below N% |
| `--jt-cov-report=TYPE` | `term`, `term-missing`, `term-verbose`, `html`, `json`, `xml` |
| `--jt-cov-exclude=PATTERN` | Exclude templates by glob |

**pyproject.toml:**
```toml
[tool.jinjatest.coverage]
enabled = true
fail_under = 80
report = ["term", "html"]
exclude_patterns = ["**/vendor/**"]
```

**Tracked:** `if`/`elif`/`else`, `for` loops, `macro`, `block`, `include`, ternary expressions

## License

MIT
