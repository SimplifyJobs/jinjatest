"""Tests for pytest plugin fixtures."""

import pytest


class TestFixtures:
    """Test pytest plugin fixtures."""

    def test_jinja_env_fixture(self, jinja_env) -> None:
        """Test that jinja_env fixture provides a configured environment."""
        from jinja2 import StrictUndefined

        assert jinja_env is not None
        assert jinja_env.undefined is StrictUndefined

    def test_template_from_string_fixture(self, template_from_string) -> None:
        """Test template_from_string fixture."""
        spec = template_from_string("Hello, {{ name }}!")
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello, World!"

    def test_template_from_string_with_model(self, template_from_string) -> None:
        """Test template_from_string with context model."""
        from pydantic import BaseModel

        class Ctx(BaseModel):
            name: str

        spec = template_from_string("Hello, {{ name }}!", context_model=Ctx)
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello, World!"

    def test_update_snapshots_fixture(self, update_snapshots) -> None:
        """Test update_snapshots fixture exists."""
        # Should be False by default (not passed --update-snapshots)
        assert update_snapshots is False


class TestSnapshotManager:
    """Test snapshot manager functionality."""

    def test_snapshot_create_and_compare(self, snapshot_manager, tmp_path) -> None:
        """Test creating and comparing snapshots."""
        # Override base_dir to use tmp_path
        snapshot_manager.base_dir = tmp_path
        snapshot_manager.update = True

        # Create snapshot
        snapshot_manager.compare_or_update("test_snap", "Hello, World!")

        # Verify file was created
        snap_file = tmp_path / "test_snap.txt"
        assert snap_file.exists()
        assert snap_file.read_text() == "Hello, World!"

        # Now compare (should pass)
        snapshot_manager.update = False
        snapshot_manager.compare_or_update("test_snap", "Hello, World!")

    def test_snapshot_mismatch(self, snapshot_manager, tmp_path) -> None:
        """Test that mismatched snapshot raises AssertionError."""
        snapshot_manager.base_dir = tmp_path
        snapshot_manager.update = True

        # Create snapshot
        snapshot_manager.compare_or_update("test_snap", "Original")

        # Try to compare with different content
        snapshot_manager.update = False
        with pytest.raises(AssertionError) as exc_info:
            snapshot_manager.compare_or_update("test_snap", "Different")

        assert "Snapshot mismatch" in str(exc_info.value)
        assert "--update-snapshots" in str(exc_info.value)


class TestTemplateSpecFactory:
    """Tests for template_spec_factory fixture."""

    def test_factory_with_absolute_path(self, tmp_path) -> None:
        """Test factory with absolute path using TemplateSpec directly."""
        from jinjatest import TemplateSpec

        # Create a template file
        template_file = tmp_path / "test.j2"
        template_file.write_text("Hello, {{ name }}!")

        # Use TemplateSpec.from_file directly since it handles loader setup
        spec = TemplateSpec.from_file(template_file)
        rendered = spec.render({"name": "World"})
        assert rendered.text == "Hello, World!"

    def test_factory_with_context_model(self, tmp_path) -> None:
        """Test factory with context model."""
        from pydantic import BaseModel

        from jinjatest import TemplateSpec

        class Ctx(BaseModel):
            name: str

        template_file = tmp_path / "model_test.j2"
        template_file.write_text("Hello, {{ name }}!")

        spec = TemplateSpec.from_file(template_file, context_model=Ctx)
        rendered = spec.render({"name": "Test"})
        assert rendered.text == "Hello, Test!"


class TestSnapshotManagerDirect:
    """Direct tests for SnapshotManager class."""

    def test_snapshot_manager_init(self, tmp_path) -> None:
        """Test SnapshotManager initialization."""
        from jinjatest.pytest_plugin import SnapshotManager

        manager = SnapshotManager(tmp_path, update=False)
        assert manager.base_dir == tmp_path
        assert manager.update is False

    def test_snapshot_manager_creates_parent_dirs(self, tmp_path) -> None:
        """Test that SnapshotManager creates parent directories."""
        from jinjatest.pytest_plugin import SnapshotManager

        nested_dir = tmp_path / "a" / "b" / "c"
        manager = SnapshotManager(nested_dir, update=True)
        manager.compare_or_update("nested_snap", "Content")

        assert (nested_dir / "nested_snap.txt").exists()

    def test_snapshot_manager_compare_existing(self, tmp_path) -> None:
        """Test comparing with existing snapshot."""
        from jinjatest.pytest_plugin import SnapshotManager

        # Pre-create snapshot
        snap_file = tmp_path / "existing.txt"
        snap_file.write_text("Expected content")

        manager = SnapshotManager(tmp_path, update=False)
        # Should not raise
        manager.compare_or_update("existing", "Expected content")

    def test_snapshot_manager_update_existing(self, tmp_path) -> None:
        """Test updating existing snapshot."""
        from jinjatest.pytest_plugin import SnapshotManager

        # Pre-create snapshot with old content
        snap_file = tmp_path / "to_update.txt"
        snap_file.write_text("Old content")

        manager = SnapshotManager(tmp_path, update=True)
        manager.compare_or_update("to_update", "New content")

        assert snap_file.read_text() == "New content"


class TestTemplateDirFixture:
    """Tests for template_dir fixture."""

    def test_template_dir_default_none(self, template_dir) -> None:
        """Test template_dir is None by default."""
        assert template_dir is None


class TestPytestPluginHooks:
    """Tests for pytest plugin configuration."""

    def test_plugin_is_loaded(self) -> None:
        """Test that the plugin is properly loaded."""
        import jinjatest.pytest_plugin as plugin

        assert hasattr(plugin, "pytest_addoption")
        assert hasattr(plugin, "pytest_configure")
        assert callable(plugin.pytest_addoption)
        assert callable(plugin.pytest_configure)
