# jinjatest

A type-safe, structured testing library for Jinja templates.

Stop writing brittle substring assertions. Test your templates with structure, validation, and confidence.

## Installation

```bash
pip install jinjatest
```

With YAML support:
```bash
pip install jinjatest[yaml]
```

## Why jinjatest?

Testing Jinja templates typically means rendering and asserting on raw strings. This is brittle (whitespace, ordering, punctuation) and doesn't scale. **jinjatest** provides:

- **Type-safe context validation** with Pydantic
- **Structured output parsing** (JSON, YAML, XML, markdown, fenced code blocks)
- **Test instrumentation** with anchors and traces
- **Pytest integration** with fixtures and snapshots
- **StrictUndefined by default** - missing variables fail loudly

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

The most robust way to test templates - assert on structure, not strings:

```jinja2
{# prompts/config.j2 #}
{% set config = {
    "model": model_name,
    "temperature": temperature,
    "features": features | default([])
} %}
{{ config | tojson }}
```

```python
def test_config_output():
    rendered = spec.render({
        "model_name": "gpt-4",
        "temperature": 0.7,
        "features": ["streaming", "tools"]
    })

    config = rendered.as_json()
    assert config["model"] == "gpt-4"
    assert config["temperature"] == 0.7
    assert "streaming" in config["features"]
```

### Structured Output (XML)

Parse XML output, including fragments with multiple root elements:

```jinja2
{# prompts/tool_calls.j2 #}
<tool name="search">
  <query>{{ query }}</query>
</tool>
{% if include_filter %}
<tool name="filter">
  <criteria>{{ filter_criteria }}</criteria>
</tool>
{% endif %}
```

```python
def test_xml_tool_calls():
    rendered = spec.render({
        "query": "python tutorials",
        "include_filter": True,
        "filter_criteria": "beginner"
    })

    # Parse as fragments (multiple roots allowed)
    tools = rendered.as_xml()  # Returns list[XMLElement]
    assert len(tools) == 2
    assert tools[0].attrib["name"] == "search"
    assert tools[0].find("query").text == "python tutorials"

    # For single-root XML, use strict=True
    # rendered.as_xml(strict=True)  # Returns XMLElement or raises
```

### Fenced Code Blocks

Extract and parse code blocks from markdown-style output:

```jinja2
{# prompts/assistant.j2 #}
Here's the configuration:

```json
{"setting": "{{ setting_name }}", "value": {{ setting_value }}}
```

And here's an alternative:

```json
{"setting": "{{ setting_name }}", "value": {{ setting_value * 2 }}}
```
```

```python
def test_fenced_json_blocks():
    rendered = spec.render({"setting_name": "timeout", "setting_value": 30})

    # Extract all ```json blocks
    configs = rendered.as_json_blocks()
    assert len(configs) == 2
    assert configs[0]["value"] == 30
    assert configs[1]["value"] == 60

# Also available:
# rendered.as_yaml_blocks()  # Extract ```yaml blocks
# rendered.as_xml_blocks()   # Extract ```xml blocks
```

### Section Testing with Anchors

Test specific sections without fragile delimiters:

```jinja2
{# prompts/chat.j2 #}
{{ jt.anchor("system") }}
System rules:
- Be helpful
- Be concise

{{ jt.anchor("user") }}
User: {{ user_name }}
Request: {{ request }}

{{ jt.anchor("context") }}
{% if context_items %}
Context:
{% for item in context_items %}
- {{ item }}
{% endfor %}
{% else %}
{{ jt.trace("no_context") }}
No additional context.
{% endif %}
```

```python
def test_sections():
    rendered = spec.render({
        "user_name": "Ada",
        "request": "Help me code",
        "context_items": ["doc1", "doc2"],
    })

    # Test sections in isolation
    assert rendered.section("user").contains("Ada")
    assert rendered.section("system").not_contains("Ada")
    assert rendered.section("context").contains("doc1")

def test_branch_coverage():
    rendered = spec.render({
        "user_name": "Ada",
        "request": "Help",
        "context_items": [],  # Empty - triggers no_context branch
    })

    # Verify which branches were taken
    assert rendered.has_trace("no_context")
```

### Macros as Functions

Test macros like regular Python functions:

```jinja2
{% macro build_prompt(user_input, context=None) %}
{% set parts = [] %}
{% do parts.append("You are a helpful assistant.") %}
{% do parts.append("User: " ~ user_input) %}
{% if context %}
{% do parts.append("Context: " ~ context) %}
{% endif %}
{{ parts | join("\n") }}
{% endmacro %}
```

```python
def test_prompt_builder():
    build_prompt = spec.macro("build_prompt")

    result = build_prompt("Hello")
    assert "User: Hello" in result
    assert "Context:" not in result

    result = build_prompt("Hello", context="Background info")
    assert "Context: Background info" in result
```

## API Reference

### TemplateSpec

```python
# From file
spec = TemplateSpec.from_file(
    "template.j2",
    context_model=MyModel,      # Optional Pydantic model
    template_dir="templates/",  # Optional base directory
    strict_undefined=True,      # Default: True
    test_mode=True,             # Enable instrumentation
)

# From string
spec = TemplateSpec.from_string(
    "Hello {{ name }}!",
    context_model=MyModel,
)

# Render
rendered = spec.render({"name": "World"})
rendered = spec.render(MyModel(name="World"))

# Access macro
my_macro = spec.macro("macro_name")
result = my_macro("arg1", "arg2")
```

### RenderedPrompt

```python
rendered.text            # Raw rendered text
rendered.normalized      # Whitespace-normalized text
rendered.clean_text      # Text with anchor markers removed
rendered.lines           # List of lines
rendered.normalized_lines # List of normalized lines

# Parsing - Full Document
rendered.as_json()               # Parse as JSON
rendered.as_yaml()               # Parse as YAML (requires pyyaml)
rendered.as_xml(strict=False)    # Parse as XML (strict=True for single root)
rendered.as_markdown_sections()  # Parse markdown headings
rendered.markdown_section("title") # Find markdown section by title

# Parsing - Fenced Code Blocks
rendered.as_json_blocks()        # Extract all ```json blocks
rendered.as_yaml_blocks()        # Extract all ```yaml blocks
rendered.as_xml_blocks()         # Extract all ```xml blocks

# Sections (with instrumentation)
rendered.section("name")         # Get section by anchor name
rendered.sections()              # Get all sections
rendered.has_section("name")     # Check if section exists

# Traces
rendered.has_trace("event")      # Check if trace was recorded
rendered.trace_count("event")    # Count occurrences of trace event
rendered.trace_events            # List of all trace events

# Query helpers
rendered.contains("text")        # Check substring exists
rendered.not_contains("text")    # Check substring doesn't exist
rendered.contains_line("text")   # Check if any line contains text
rendered.has_line("exact line")  # Check if exact line exists
rendered.matches(r"pattern")     # Check regex matches
rendered.find_all(r"pattern")    # Find all regex matches
```

### PromptAsserts

```python
a = PromptAsserts(rendered)
a = PromptAsserts(rendered).normalized()  # Use normalized text

# Chainable assertions
a.contains("text")
a.not_contains("text")
a.contains_line("partial line match")
a.has_exact_line("exact line")
a.regex(r"pattern")
a.not_regex(r"pattern")
a.equals("exact text")
a.equals_json({"key": "value"})
a.line_count(5)
a.line_count_between(3, 10)

# Trace assertions
a.has_trace("event")
a.not_has_trace("event")

# Snapshots
a.snapshot("snapshot_name", update=False)
```

### Instrumentation

In templates:
```jinja2
{{ jt.anchor("section_name") }}  {# Mark section start #}
{{ jt.trace("event_name") }}     {# Record trace event #}
```

#### Using with Any Jinja Environment

You can add instrumentation to any Jinja environment using `instrument()`:

```python
from jinja2 import Environment, FileSystemLoader
from jinjatest import instrument

# Patch any existing Jinja environment
env = Environment(loader=FileSystemLoader("templates/"))
inst = instrument(env)  # Adds `jt` global

# Now templates can use {{ jt.anchor("x") }} and {{ jt.trace("y") }}
template = env.get_template("my_template.j2")
result = template.render({"name": "World"})

# Check traces after rendering
if inst.has_trace("some_event"):
    print("Event was triggered")

# For production, use test_mode=False (anchors/traces become no-ops)
instrument(env, test_mode=False)
```

This is useful when you want to add instrumentation to an existing Jinja setup without using `TemplateSpec`.

## Pytest Integration

jinjatest provides pytest fixtures automatically:

```python
def test_with_fixtures(template_from_string, jinja_env):
    spec = template_from_string("Hello {{ name }}!")
    rendered = spec.render({"name": "World"})
    assert rendered.text == "Hello World!"

def test_with_snapshots(snapshot_manager, template_from_string):
    spec = template_from_string("Hello {{ name }}!")
    rendered = spec.render({"name": "World"})
    snapshot_manager.compare_or_update("greeting", rendered.text)
```

Update snapshots:
```bash
pytest --update-snapshots
```

## Advanced Configuration

### Custom Environment

```python
from jinjatest import create_environment, TemplateSpec

env = create_environment(
    template_paths=["templates/", "shared/"],
    mock_templates={"header.j2": "Mock Header"},
    strict_undefined=True,
    enable_do_extension=True,
    sandboxed=False,
    filters={"my_filter": lambda x: x.upper()},
    globals={"version": "1.0"},
)

spec = TemplateSpec.from_file("template.j2", env=env)
```

### Variable Validation (CI Guardrails)

```python
spec = TemplateSpec.from_file("template.j2")

# Fail if template uses unexpected variables
spec.assert_variables_subset_of({"user_name", "plan", "items"})
```

## License

MIT
