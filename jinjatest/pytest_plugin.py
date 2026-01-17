"""
Pytest plugin for jinjatest.

Provides fixtures and configuration for testing Jinja templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import pytest
from jinja2 import Environment

from jinjatest.spec import TemplateSpec, create_environment

if TYPE_CHECKING:
    from pydantic import BaseModel


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for jinjatest."""
    group = parser.getgroup("jinjatest", "Jinja template testing")
    group.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshot files instead of comparing",
    )
    group.addoption(
        "--template-dir",
        action="store",
        default=None,
        help="Default directory for template files",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure jinjatest markers."""
    config.addinivalue_line(
        "markers",
        "template(path): mark test as using a specific template file",
    )


@pytest.fixture
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    """Fixture that returns True if --update-snapshots was passed."""
    return request.config.getoption("--update-snapshots", default=False)


@pytest.fixture
def template_dir(request: pytest.FixtureRequest) -> Path | None:
    """Fixture that returns the configured template directory."""
    dir_opt = request.config.getoption("--template-dir", default=None)
    if dir_opt:
        return Path(dir_opt)
    return None


@pytest.fixture
def jinja_env() -> Environment:
    """Fixture providing a default Jinja Environment for testing.

    The environment is configured with:
    - StrictUndefined (raises on undefined variables)
    - jinja2.ext.do extension enabled
    - Test instrumentation enabled

    Override this fixture if you need custom configuration.
    """
    return create_environment(
        strict_undefined=True,
        enable_do_extension=True,
    )


@pytest.fixture
def template_spec_factory(
    jinja_env: Environment,
    template_dir: Path | None,
) -> Callable[..., TemplateSpec[Any]]:
    """Fixture providing a factory for creating TemplateSpec instances.

    Usage:
        def test_something(template_spec_factory):
            spec = template_spec_factory("path/to/template.j2", context_model=MyModel)
            rendered = spec.render({"key": "value"})
            assert "expected" in rendered.text

    Args:
        jinja_env: The Jinja Environment fixture.
        template_dir: The template directory fixture.

    Returns:
        A factory function for creating TemplateSpec instances.
    """

    def factory(
        path: str | Path,
        *,
        context_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> TemplateSpec[Any]:
        """Create a TemplateSpec for the given template path.

        Args:
            path: Path to the template file.
            context_model: Optional Pydantic model for context validation.
            **kwargs: Additional arguments passed to TemplateSpec.from_file.

        Returns:
            A configured TemplateSpec.
        """
        base_dir = template_dir or Path.cwd()
        full_path = base_dir / path if not Path(path).is_absolute() else Path(path)

        return TemplateSpec.from_file(
            full_path,
            context_model=context_model,
            env=jinja_env,
            **kwargs,
        )

    return factory


@pytest.fixture
def template_from_string(
    jinja_env: Environment,
) -> Callable[..., TemplateSpec[Any]]:
    """Fixture providing a factory for creating TemplateSpec from strings.

    Useful for inline template testing without creating template files.

    Usage:
        def test_inline_template(template_from_string):
            spec = template_from_string("Hello {{ name }}!")
            rendered = spec.render({"name": "World"})
            assert rendered.text == "Hello World!"

    Args:
        jinja_env: The Jinja Environment fixture.

    Returns:
        A factory function for creating TemplateSpec from strings.
    """

    def factory(
        source: str,
        *,
        context_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> TemplateSpec[Any]:
        """Create a TemplateSpec from a template string.

        Args:
            source: The template source code.
            context_model: Optional Pydantic model for context validation.
            **kwargs: Additional arguments passed to TemplateSpec.from_string.

        Returns:
            A configured TemplateSpec.
        """
        return TemplateSpec.from_string(
            source,
            context_model=context_model,
            env=jinja_env,
            **kwargs,
        )

    return factory


class SnapshotManager:
    """Helper class for managing test snapshots."""

    def __init__(
        self,
        base_dir: Path,
        update: bool = False,
    ) -> None:
        self.base_dir = base_dir
        self.update = update

    def compare_or_update(self, name: str, content: str) -> None:
        """Compare content against snapshot or update it.

        Args:
            name: The snapshot name.
            content: The content to compare/save.

        Raises:
            AssertionError: If snapshot doesn't match and update is False.
        """
        snapshot_path = self.base_dir / f"{name}.txt"

        if self.update or not snapshot_path.exists():
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(content)
            return

        expected = snapshot_path.read_text()
        if content != expected:
            raise AssertionError(
                f"Snapshot mismatch for '{name}'.\n"
                f"Expected:\n{expected}\n\n"
                f"Actual:\n{content}\n\n"
                f"Run with --update-snapshots to update."
            )


@pytest.fixture
def snapshot_manager(
    request: pytest.FixtureRequest,
    update_snapshots: bool,
) -> SnapshotManager:
    """Fixture providing a SnapshotManager for the current test.

    Snapshots are stored in tests/__snapshots__/<test_module>/<test_name>/

    Usage:
        def test_something(snapshot_manager, template_from_string):
            spec = template_from_string("Hello {{ name }}!")
            rendered = spec.render({"name": "World"})
            snapshot_manager.compare_or_update("output", rendered.text)

    Args:
        request: The pytest request fixture.
        update_snapshots: Whether to update snapshots.

    Returns:
        A configured SnapshotManager.
    """
    # Determine snapshot directory based on test location
    test_path = Path(request.path) if request.path else Path.cwd()
    test_name = request.node.name

    # Create path: tests/__snapshots__/<module>/<test_name>/
    snapshot_dir = test_path.parent / "__snapshots__" / test_path.stem / test_name

    return SnapshotManager(snapshot_dir, update=update_snapshots)
