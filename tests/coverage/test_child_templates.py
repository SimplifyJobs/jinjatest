"""Tests for coverage of child templates loaded via include/import/from/extends."""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from jinja2 import (
    BaseLoader,
    Environment,
    FileSystemLoader,
    Template,
    TemplateNotFound,
)

from jinjatest import TemplateSpec
from jinjatest.coverage.collector import (
    get_coverage_collector,
    reset_coverage_collector,
)
from jinjatest.coverage.loader import CoverageLoader


class TestIncludedTemplateCoverage:
    """Templates loaded via {% include %} are registered and tracked."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_include_child_is_tracked(self, tmp_path: Path) -> None:
        """Test that an included template gets its own coverage tracker."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text("{% if flag %}yes{% else %}no{% endif %}")

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"flag": True})

        assert "yes" in rendered.text

        child_tracker = collector.get_tracker("child.j2")
        assert child_tracker is not None
        assert child_tracker.get_hit_count("if_1_true") == 1

    def test_include_child_hits_not_absorbed_by_parent(self, tmp_path: Path) -> None:
        """Test that child branch hits are not attributed to the parent."""
        collector = get_coverage_collector()
        collector.enable()

        # Parent has an if on line 1 producing the same bare branch id
        # (if_1_true) as the child's if on its own line 1.
        (tmp_path / "main.j2").write_text(
            '{% if show %}{% include "child.j2" %}{% endif %}'
        )
        (tmp_path / "child.j2").write_text("{% if flag %}yes{% else %}no{% endif %}")

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"show": True, "flag": True})

        child_tracker = collector.get_tracker("child.j2")
        assert child_tracker is not None
        assert child_tracker.get_hit_count("if_1_true") == 1

        parent_tracker = collector.get_tracker(str((tmp_path / "main.j2").resolve()))
        assert parent_tracker is not None
        # Only the parent's own if fired once; the child's same-named branch
        # must not be absorbed into the parent tracker.
        assert parent_tracker.get_hit_count("if_1_true") == 1

        # Child events are namespaced in the recorded trace events.
        assert "child.j2::if_1_true" in rendered.trace_events

    def test_include_child_false_branch(self, tmp_path: Path) -> None:
        """Test that a child's else branch is tracked when taken."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text("{% if flag %}yes{% else %}no{% endif %}")

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"flag": False})

        assert "no" in rendered.text

        child_tracker = collector.get_tracker("child.j2")
        assert child_tracker is not None
        assert child_tracker.get_hit_count("if_1_false") == 1

    def test_include_child_ternary_tracked(self, tmp_path: Path) -> None:
        """Test that CondExpr branches inside an included template are tracked."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text('{{ "yes" if flag else "no" }}')

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"flag": True})

        assert "yes" in rendered.text

        child_tracker = collector.get_tracker("child.j2")
        assert child_tracker is not None
        assert child_tracker.get_hit_count("ternary_1_true") == 1

    def test_nested_include_grandchild_tracked(self, tmp_path: Path) -> None:
        """Test that transitively included templates are tracked too."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text('{% include "grand.j2" %}')
        (tmp_path / "grand.j2").write_text("{% if x %}deep{% endif %}")

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"x": True})

        assert "deep" in rendered.text

        grand_tracker = collector.get_tracker("grand.j2")
        assert grand_tracker is not None
        assert grand_tracker.get_hit_count("if_1_true") == 1

    def test_include_not_tracked_when_coverage_disabled(self, tmp_path: Path) -> None:
        """Test that included templates are not tracked when coverage is off."""
        collector = get_coverage_collector()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text("{% if flag %}yes{% endif %}")

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({"flag": True})

        assert "yes" in rendered.text
        assert collector.get_tracker("child.j2") is None


class TestImportedTemplateCoverage:
    """Templates loaded via {% import %}/{% from %} are registered and tracked."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_import_child_is_tracked(self, tmp_path: Path) -> None:
        """Test that an imported macro library gets coverage tracking."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text(
            '{% import "lib.j2" as lib %}{{ lib.m(True) }}'
        )
        (tmp_path / "lib.j2").write_text(
            "{% macro m(v) %}{% if v %}T{% else %}F{% endif %}{% endmacro %}"
        )

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({})

        assert "T" in rendered.text

        tracker = collector.get_tracker("lib.j2")
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1
        assert tracker.get_hit_count("macro_m") == 1

    def test_from_import_child_is_tracked(self, tmp_path: Path) -> None:
        """Test that a from-imported macro library gets coverage tracking."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% from "lib.j2" import m %}{{ m(False) }}')
        (tmp_path / "lib.j2").write_text(
            "{% macro m(v) %}{% if v %}T{% else %}F{% endif %}{% endmacro %}"
        )

        spec = TemplateSpec.from_file(tmp_path / "main.j2", template_dir=tmp_path)
        rendered = spec.render({})

        assert "F" in rendered.text

        tracker = collector.get_tracker("lib.j2")
        assert tracker is not None
        assert tracker.get_hit_count("if_1_false") == 1

    def test_from_string_with_mock_template_include(self) -> None:
        """Test child coverage when the loader comes from mock_templates."""
        collector = get_coverage_collector()
        collector.enable()

        spec = TemplateSpec.from_string(
            '{% include "partial.j2" %}',
            mock_templates={"partial.j2": "{% if x %}yes{% else %}no{% endif %}"},
        )
        rendered = spec.render({"x": True})

        assert "yes" in rendered.text

        tracker = collector.get_tracker("partial.j2")
        assert tracker is not None
        assert tracker.get_hit_count("if_1_true") == 1


class TestExtendedTemplateCoverage:
    """Templates loaded via {% extends %} are registered and tracked."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_extends_parent_is_tracked(self, tmp_path: Path) -> None:
        """Test that a parent template used via {% extends %} is tracked."""
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "base.j2").write_text(
            "{% block content %}base{% endblock %}\n"
            "{% block footer %}{% if f %}F{% else %}f{% endif %}{% endblock %}"
        )
        (tmp_path / "child.j2").write_text(
            '{% extends "base.j2" %}'
            "{% block content %}{% if x %}A{% endif %}{% endblock %}"
        )

        spec = TemplateSpec.from_file(tmp_path / "child.j2", template_dir=tmp_path)
        rendered = spec.render({"x": True, "f": True})

        assert "A" in rendered.text
        assert "F" in rendered.text

        base_tracker = collector.get_tracker("base.j2")
        assert base_tracker is not None
        # The non-overridden footer block runs the parent's instrumented code.
        assert base_tracker.get_hit_count("if_2_true") == 1
        assert base_tracker.get_hit_count("block_footer") == 1


class PrecompiledLoader(BaseLoader):
    """Serves 'precompiled' templates without source access.

    Mimics jinja2.ModuleLoader: ``has_source_access`` is False and
    ``load`` is overridden so ``get_source`` (which would raise) is never
    consulted.
    """

    has_source_access = False

    def __init__(self, sources: dict[str, str]) -> None:
        self._sources = sources

    def load(
        self,
        environment: Environment,
        name: str,
        globals: MutableMapping[str, Any] | None = None,
    ) -> Template:
        """Return a compiled template, bypassing get_source entirely."""
        if name not in self._sources:
            raise TemplateNotFound(name)
        if globals is None:
            globals = {}
        code = environment.compile(self._sources[name], name)
        return environment.template_class.from_code(environment, code, globals)


class TestLoaderWithoutSourceAccess:
    """Loaders without source access must not be wrapped."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_loader_without_source_access_is_not_wrapped(self) -> None:
        """Test that a precompiled-template loader is left unwrapped.

        Wrapping it would route child lookups through
        CoverageLoader.get_source, which such loaders do not support.
        Children keep rendering, just without coverage instrumentation.
        """
        collector = get_coverage_collector()
        collector.enable()

        loader = PrecompiledLoader({"child.j2": "precompiled child"})
        env = Environment(loader=loader)

        spec = TemplateSpec.from_string('{% include "child.j2" %}', env=env)
        rendered = spec.render({})

        # Render still works through the unwrapped loader.
        assert "precompiled child" in rendered.text
        assert env.loader is loader
        assert not isinstance(env.loader, CoverageLoader)
        assert collector.get_tracker("child.j2") is None


class TestStaleCacheCleared:
    """Re-spec'ing a reused env must clear cached compiled children."""

    def setup_method(self) -> None:
        """Reset coverage collector before each test."""
        reset_coverage_collector()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_coverage_collector()

    def test_child_retracked_after_collector_reset(self, tmp_path: Path) -> None:
        """Test that a child re-registers after the collector is reset.

        The reused env's cache holds the child compiled under the old run;
        without a cache clear, the second render would serve it from cache
        and the child would never re-register with the collector.
        """
        collector = get_coverage_collector()
        collector.enable()

        (tmp_path / "main.j2").write_text('{% include "child.j2" %}')
        (tmp_path / "child.j2").write_text("{% if flag %}yes{% else %}no{% endif %}")

        env = Environment(loader=FileSystemLoader(str(tmp_path)))

        spec = TemplateSpec.from_file("main.j2", env=env)
        rendered = spec.render({"flag": True})

        assert "yes" in rendered.text
        assert collector.get_tracker("child.j2") is not None

        # Simulate a new coverage run on the same env: trackers are wiped
        # but the loader stays wrapped, so a stale cache would serve the
        # child compiled under the previous run without re-registering it.
        collector.reset()

        spec = TemplateSpec.from_file("main.j2", env=env)
        rendered = spec.render({"flag": False})

        assert "no" in rendered.text

        child_tracker = collector.get_tracker("child.j2")
        assert child_tracker is not None
        assert child_tracker.get_hit_count("if_1_false") == 1
