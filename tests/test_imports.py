"""Tests for package imports and exports."""

import jinjatest
from jinjatest import parsers


class TestMainPackageExports:
    """Tests for jinjatest package exports."""

    def test_version_available(self):
        assert hasattr(jinjatest, "__version__")
        assert isinstance(jinjatest.__version__, str)

    def test_version_matches_package_metadata(self):
        """__version__ must stay in sync with the release in pyproject.toml."""
        import importlib.metadata

        assert jinjatest.__version__ == importlib.metadata.version("jinjatest")

    def test_all_exports_in_namespace(self):
        """All items in __all__ should be accessible."""
        for name in jinjatest.__all__:
            assert hasattr(jinjatest, name), f"{name} not accessible from jinjatest"

    def test_core_classes_exported(self):
        from jinjatest import RenderedPrompt, RenderedPromptSection, TemplateSpec

        assert TemplateSpec is not None
        assert RenderedPrompt is not None
        assert RenderedPromptSection is not None

    def test_assertion_classes_exported(self):
        from jinjatest import PromptAssertionError, PromptAsserts, assert_no_undefined

        assert PromptAsserts is not None
        assert PromptAssertionError is not None
        assert assert_no_undefined is not None

    def test_exception_classes_exported(self):
        from jinjatest import (
            ContextValidationError,
            JSONParseError,
            TemplateRenderError,
            UndeclaredVariableError,
            XMLParseError,
        )

        assert TemplateRenderError is not None
        assert ContextValidationError is not None
        assert UndeclaredVariableError is not None
        assert JSONParseError is not None
        assert XMLParseError is not None

    def test_parser_functions_exported(self):
        from jinjatest import parse_json, parse_markdown_sections, parse_xml

        assert callable(parse_json)
        assert callable(parse_xml)
        assert callable(parse_markdown_sections)

    def test_parser_models_exported(self):
        from jinjatest import MarkdownSection, XMLElement

        assert MarkdownSection is not None
        assert XMLElement is not None

    def test_fenced_block_exports(self):
        from jinjatest import FencedBlock, extract_fenced_blocks, parse_fenced_blocks

        assert callable(extract_fenced_blocks)
        assert callable(parse_fenced_blocks)
        assert FencedBlock is not None

    def test_instrumentation_exported(self):
        from jinjatest import (
            ProductionInstrumentation,
            TestInstrumentation,
        )

        assert TestInstrumentation is not None
        assert ProductionInstrumentation is not None

    def test_utilities_exported(self):
        from jinjatest import create_environment, normalize_text

        assert callable(normalize_text)
        assert callable(create_environment)

    def test_yaml_exports_available(self):
        """YAML exports should be available when pyyaml is installed."""
        from jinjatest import YAMLParseError, parse_yaml

        assert callable(parse_yaml)
        assert YAMLParseError is not None
        assert "parse_yaml" in jinjatest.__all__
        assert "YAMLParseError" in jinjatest.__all__


class TestParsersPackageExports:
    """Tests for jinjatest.parsers package exports."""

    def test_all_exports_in_namespace(self):
        """All items in __all__ should be accessible."""
        for name in parsers.__all__:
            assert hasattr(parsers, name), (
                f"{name} not accessible from jinjatest.parsers"
            )

    def test_json_exports(self):
        from jinjatest.parsers import JSONParseError, parse_json

        assert callable(parse_json)
        assert JSONParseError is not None

    def test_markdown_exports(self):
        from jinjatest.parsers import MarkdownSection, parse_markdown_sections

        assert callable(parse_markdown_sections)
        assert MarkdownSection is not None

    def test_xml_exports(self):
        from jinjatest.parsers import XMLElement, XMLParseError, parse_xml

        assert callable(parse_xml)
        assert XMLParseError is not None
        assert XMLElement is not None

    def test_fenced_block_exports(self):
        from jinjatest.parsers import (
            FencedBlock,
            extract_fenced_blocks,
            parse_fenced_blocks,
        )

        assert callable(extract_fenced_blocks)
        assert callable(parse_fenced_blocks)
        assert FencedBlock is not None

    def test_yaml_exports_available(self):
        """YAML exports should be available when pyyaml is installed."""
        from jinjatest.parsers import YAMLParseError, parse_yaml

        assert callable(parse_yaml)
        assert YAMLParseError is not None
        assert "parse_yaml" in parsers.__all__
        assert "YAMLParseError" in parsers.__all__


class TestDirectSubmoduleImports:
    """Tests for importing directly from submodules."""

    def test_import_from_json_parser(self):
        from jinjatest.parsers.json_parser import JSONParseError, parse_json

        assert callable(parse_json)
        assert JSONParseError is not None

    def test_import_from_yaml_parser(self):
        from jinjatest.parsers.yaml_parser import YAMLParseError, parse_yaml

        assert callable(parse_yaml)
        assert YAMLParseError is not None

    def test_import_from_markdown(self):
        from jinjatest.parsers.markdown import MarkdownSection, parse_markdown_sections

        assert callable(parse_markdown_sections)
        assert MarkdownSection is not None

    def test_import_from_xml_parser(self):
        from jinjatest.parsers.xml_parser import XMLElement, XMLParseError, parse_xml

        assert callable(parse_xml)
        assert XMLParseError is not None
        assert XMLElement is not None

    def test_import_from_fenced_blocks(self):
        from jinjatest.parsers.fenced_blocks import (
            FencedBlock,
            extract_fenced_blocks,
            parse_fenced_blocks,
        )

        assert callable(extract_fenced_blocks)
        assert callable(parse_fenced_blocks)
        assert FencedBlock is not None

    def test_import_from_spec(self):
        from jinjatest.spec import (
            ContextValidationError,
            TemplateRenderError,
            TemplateSpec,
            UndeclaredVariableError,
            create_environment,
        )

        assert TemplateSpec is not None
        assert TemplateRenderError is not None
        assert ContextValidationError is not None
        assert UndeclaredVariableError is not None
        assert callable(create_environment)

    def test_import_from_rendered(self):
        from jinjatest.rendered import (
            RenderedPrompt,
            RenderedPromptSection,
            normalize_text,
        )

        assert RenderedPrompt is not None
        assert RenderedPromptSection is not None
        assert callable(normalize_text)

    def test_import_from_asserts(self):
        from jinjatest.asserts import (
            PromptAssertionError,
            PromptAsserts,
            assert_no_undefined,
        )

        assert PromptAsserts is not None
        assert PromptAssertionError is not None
        assert callable(assert_no_undefined)

    def test_import_from_instrumentation(self):
        from jinjatest.instrumentation import (
            AnchorIndex,
            ProductionInstrumentation,
            TestInstrumentation,
            TraceRecorder,
            create_instrumentation,
        )

        assert callable(create_instrumentation)
        assert TestInstrumentation is not None
        assert ProductionInstrumentation is not None
        assert TraceRecorder is not None
        assert AnchorIndex is not None
