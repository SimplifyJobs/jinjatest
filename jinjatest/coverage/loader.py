"""Coverage-aware Jinja2 loader wrapper.

This module provides a loader wrapper that registers and instruments
templates loaded at render time (via {% include %}, {% import %},
{% from %}, or {% extends %}) with the coverage collector.
"""

from __future__ import annotations

import typing as t

from jinja2 import BaseLoader

if t.TYPE_CHECKING:
    from jinja2 import Environment


class CoverageLoader(BaseLoader):
    """Loader wrapper that instruments loaded templates for coverage.

    Delegates template resolution to the wrapped loader. When the global
    coverage collector is enabled, each loaded template is registered under
    its loader name and compiled from instrumented source that emits
    namespaced trace events ("<name>::<branch_id>"), so child-template
    branches are attributed to the correct tracker.

    The root template is not affected: TemplateSpec compiles it directly
    from source and registers it under its own coverage path.
    """

    def __init__(self, wrapped: BaseLoader) -> None:
        """Initialize the coverage loader.

        Args:
            wrapped: The real loader to delegate template loading to.
        """
        self.wrapped = wrapped
        self.has_source_access = wrapped.has_source_access

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, t.Callable[[], bool] | None]:
        """Get the template source, instrumented when coverage is enabled.

        Args:
            environment: The Jinja environment.
            template: The template name.

        Returns:
            Tuple of (source, filename, uptodate) where source is the
            instrumented source when coverage collection is enabled.
        """
        source, filename, uptodate = self.wrapped.get_source(environment, template)

        from jinjatest.coverage.collector import get_coverage_collector

        collector = get_coverage_collector()
        source = collector.register_template(
            template, source, event_prefix=f"{template}::"
        )

        return source, filename, uptodate

    def list_templates(self) -> list[str]:
        """List available templates, delegated to the wrapped loader.

        Returns:
            List of template names.
        """
        return self.wrapped.list_templates()


def unwrap_loader(loader: BaseLoader | None) -> BaseLoader | None:
    """Return the inner loader when `loader` is a CoverageLoader.

    Used when reading raw template source (e.g., for the root template)
    so the unmodified source is registered instead of an already
    instrumented one.

    Args:
        loader: The loader to unwrap.

    Returns:
        The wrapped loader if `loader` is a CoverageLoader, else `loader`.
    """
    if isinstance(loader, CoverageLoader):
        return loader.wrapped
    return loader
