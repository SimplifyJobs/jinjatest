"""
TemplateSpec: The core class for loading and rendering Jinja templates.

Provides a type-safe, test-friendly interface for working with Jinja templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    DictLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    UndefinedError,
    meta,
)
from jinja2.nativetypes import NativeEnvironment
from pydantic import BaseModel, ValidationError

from jinjatest.instrumentation import (
    AnchorIndex,
    ProductionInstrumentation,
    TestInstrumentation,
    create_instrumentation,
    instrument,
)
from jinjatest.markers import transform_markers
from jinjatest.rendered import RenderedPrompt

# Type alias for instrumentation
Instrumentation = TestInstrumentation | ProductionInstrumentation

if TYPE_CHECKING:
    from collections.abc import Mapping

# Type variable for context model
TContext = TypeVar("TContext", bound=BaseModel)


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class ContextValidationError(Exception):
    """Raised when context validation fails."""

    def __init__(
        self, message: str, validation_errors: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors or []


class UndeclaredVariableError(Exception):
    """Raised when template uses undeclared variables."""

    def __init__(self, variables: set[str], allowed: set[str]) -> None:
        self.variables = variables
        self.allowed = allowed
        extra = variables - allowed
        super().__init__(
            f"Template uses undeclared variables: {extra}. Allowed: {allowed}"
        )


def create_environment(
    *,
    loader: BaseLoader | None = None,
    template_paths: list[str | Path] | None = None,
    mock_templates: dict[str, str] | None = None,
    strict_undefined: bool = True,
    enable_do_extension: bool = True,
    sandboxed: bool = False,
    native_types: bool = False,
    extensions: list[str] | None = None,
    filters: dict[str, Callable[..., Any]] | None = None,
    globals: dict[str, Any] | None = None,
    tests: dict[str, Callable[..., bool]] | None = None,
) -> Environment:
    """Create a configured Jinja Environment.

    Args:
        loader: Custom loader. If not provided, one is built from template_paths and mock_templates.
        template_paths: Directories to load templates from.
        mock_templates: Dictionary of template name -> template content for mocking.
        strict_undefined: If True, use StrictUndefined (raises on undefined vars).
        enable_do_extension: If True, enable jinja2.ext.do for statement expressions.
        sandboxed: If True, use SandboxedEnvironment for untrusted templates.
        native_types: If True, use NativeEnvironment for Python type output.
        extensions: Additional Jinja extensions to load.
        filters: Custom filters to add to the environment.
        globals: Global variables/functions to add to the environment.
        tests: Custom tests to add to the environment.

    Returns:
        Configured Jinja Environment.
    """
    # Build loader if not provided
    if loader is None:
        loaders: list[BaseLoader] = []

        if mock_templates:
            loaders.append(DictLoader(mock_templates))

        if template_paths:
            for path in template_paths:
                loaders.append(FileSystemLoader(str(path)))

        if loaders:
            loader = ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0]

    # Build extensions list
    env_extensions: list[str] = []
    if enable_do_extension:
        env_extensions.append("jinja2.ext.do")
    if extensions:
        env_extensions.extend(extensions)

    # Choose environment class
    if sandboxed:
        from jinja2.sandbox import SandboxedEnvironment

        env_class = SandboxedEnvironment
    elif native_types:
        env_class = NativeEnvironment  # type: ignore[assignment]
    else:
        env_class = Environment

    # Create environment
    env = env_class(
        loader=loader,
        undefined=StrictUndefined if strict_undefined else None,
        extensions=env_extensions if env_extensions else [],
    )

    # Add custom filters
    if filters:
        env.filters.update(filters)

    # Add custom globals
    if globals:
        env.globals.update(globals)

    # Add custom tests
    if tests:
        env.tests.update(tests)

    return env


class TemplateSpec(Generic[TContext]):
    """A template specification that compiles once and renders many times.

    Type-safe wrapper around Jinja templates with validation and rendering helpers.

    Example:
        from pydantic import BaseModel

        class Ctx(BaseModel):
            user_name: str
            plan: str

        spec = TemplateSpec.from_file("prompts/welcome.j2", context_model=Ctx)
        rendered = spec.render({"user_name": "Ada", "plan": "pro"})
        assert "Hello, Ada" in rendered.text
    """

    def __init__(
        self,
        template: Template,
        *,
        env: Environment,
        context_model: type[TContext] | None = None,
        instrumentation: Instrumentation | None = None,
        source: str | None = None,
    ) -> None:
        """Initialize a TemplateSpec.

        Args:
            template: The compiled Jinja Template.
            env: The Jinja Environment.
            context_model: Optional Pydantic model for context validation.
            instrumentation: Optional instrumentation for anchors/traces.
            source: Optional original template source (used for AST analysis).
        """
        self._template = template
        self._env = env
        self._context_model = context_model
        self._instrumentation: Instrumentation = (
            instrumentation or create_instrumentation(test_mode=True)
        )
        self._source = source

    @classmethod
    def from_string(
        cls,
        source: str,
        *,
        context_model: type[TContext] | None = None,
        env: Environment | None = None,
        test_mode: bool = True,
        use_comment_markers: bool = True,
        **env_kwargs: Any,
    ) -> TemplateSpec[TContext]:
        """Create a TemplateSpec from a template string.

        Args:
            source: The template source code.
            context_model: Optional Pydantic model for context validation.
            env: Optional pre-configured Environment.
            test_mode: If True, enable instrumentation.
            use_comment_markers: If True, transform {#jt:...#} comments to function calls.
                Only applies when test_mode is True. Default True.
            **env_kwargs: Arguments passed to create_environment if env is None.

        Returns:
            A configured TemplateSpec.
        """
        # Transform comment markers if enabled and in test mode
        if use_comment_markers and test_mode:
            transform_result = transform_markers(source)
            source = transform_result.source

        if env is None:
            env = create_environment(**env_kwargs)

        instrumentation = instrument(env, test_mode=test_mode)

        template = env.from_string(source)
        return cls(
            template,
            env=env,
            context_model=context_model,
            instrumentation=instrumentation if test_mode else None,
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        context_model: type[TContext] | None = None,
        env: Environment | None = None,
        test_mode: bool = True,
        use_comment_markers: bool = True,
        template_dir: str | Path | None = None,
        **env_kwargs: Any,
    ) -> TemplateSpec[TContext]:
        """Create a TemplateSpec from a template file.

        Args:
            path: Path to the template file.
            context_model: Optional Pydantic model for context validation.
            env: Optional pre-configured Environment.
            test_mode: If True, enable instrumentation.
            use_comment_markers: If True, transform {#jt:...#} comments to function calls.
                Only applies when test_mode is True. Default True.
            template_dir: Base directory for template loading. If None, uses parent of path.
            **env_kwargs: Arguments passed to create_environment if env is None.

        Returns:
            A configured TemplateSpec.
        """
        path = Path(path)

        if env is None:
            # Determine template directory
            if template_dir is None:
                template_dir = path.parent
            else:
                template_dir = Path(template_dir)

            # Set up template paths
            template_paths = env_kwargs.pop("template_paths", None) or []
            template_paths = [template_dir] + [Path(p) for p in template_paths]

            env = create_environment(template_paths=template_paths, **env_kwargs)

        instrumentation = instrument(env, test_mode=test_mode)

        # If using comment markers and in test mode, read and transform the source
        original_source: str | None = None
        if use_comment_markers and test_mode:
            # Read the raw source from file
            full_path = path if path.is_absolute() else Path(template_dir or ".") / path
            original_source = full_path.read_text()

            # Transform markers
            transform_result = transform_markers(original_source)

            # Compile from transformed source
            template = env.from_string(transform_result.source)
        else:
            # Get template name relative to loader
            template_name = path.name
            template = env.get_template(template_name)

        return cls(
            template,
            env=env,
            context_model=context_model,
            instrumentation=instrumentation if test_mode else None,
            source=original_source,
        )

    @property
    def env(self) -> Environment:
        """Get the Jinja Environment."""
        return self._env

    @property
    def template(self) -> Template:
        """Get the compiled Template."""
        return self._template

    @property
    def context_model(self) -> type[TContext] | None:
        """Get the context model class if set."""
        return self._context_model

    def _validate_context(self, context: Mapping[str, Any]) -> dict[str, Any]:
        """Validate context against the model if set.

        Args:
            context: The context dictionary.

        Returns:
            Validated context dictionary.

        Raises:
            ContextValidationError: If validation fails.
        """
        if self._context_model is None:
            return dict(context)

        try:
            validated = self._context_model.model_validate(context)
            return validated.model_dump()
        except ValidationError as e:
            errors = e.errors()
            error_msgs = [f"  - {err['loc']}: {err['msg']}" for err in errors]
            raise ContextValidationError(
                "Context validation failed:\n" + "\n".join(error_msgs),
                validation_errors=[dict(err) for err in errors],
            ) from e

    @overload
    def render(self, context: TContext) -> RenderedPrompt: ...

    @overload
    def render(self, context: Mapping[str, Any]) -> RenderedPrompt: ...

    def render(self, context: TContext | Mapping[str, Any]) -> RenderedPrompt:
        """Render the template with the given context.

        Args:
            context: Either a Pydantic model instance or a dictionary.

        Returns:
            A RenderedPrompt with the rendered text and metadata.

        Raises:
            ContextValidationError: If context validation fails.
            TemplateRenderError: If rendering fails.
        """
        # Clear instrumentation from previous render
        if self._instrumentation:
            self._instrumentation.clear()

        # Convert Pydantic model to dict if needed
        if isinstance(context, BaseModel):
            ctx_dict = context.model_dump()
        else:
            ctx_dict = self._validate_context(context)

        try:
            text = self._template.render(ctx_dict)
        except UndefinedError as e:
            raise TemplateRenderError(
                f"Undefined variable in template: {e}", original_error=e
            ) from e
        except Exception as e:
            raise TemplateRenderError(
                f"Template rendering failed: {e}", original_error=e
            ) from e

        # Process instrumentation
        trace_events: list[str] = []
        anchor_index: AnchorIndex | None = None

        if self._instrumentation:
            trace_events = self._instrumentation.trace_events
            anchor_index = AnchorIndex.from_text(text)

        return RenderedPrompt(
            text=text,
            trace_events=trace_events,
            anchor_index=anchor_index,
        )

    def render_native(self, context: TContext | Mapping[str, Any]) -> Any:
        """Render template to native Python types (requires NativeEnvironment).

        This is useful when templates output structured data like JSON.

        Args:
            context: The context dictionary or Pydantic model.

        Returns:
            The rendered value as a native Python type.

        Raises:
            ContextValidationError: If context validation fails.
            TemplateRenderError: If rendering fails.
        """
        if isinstance(context, BaseModel):
            ctx_dict = context.model_dump()
        else:
            ctx_dict = self._validate_context(context)

        try:
            return self._template.render(ctx_dict)
        except UndefinedError as e:
            raise TemplateRenderError(
                f"Undefined variable in template: {e}", original_error=e
            ) from e
        except Exception as e:
            raise TemplateRenderError(
                f"Template rendering failed: {e}", original_error=e
            ) from e

    def macro(self, name: str) -> Callable[..., str]:
        """Get a macro from the template as a callable.

        Args:
            name: The name of the macro.

        Returns:
            A callable that invokes the macro.

        Raises:
            AttributeError: If macro doesn't exist.
        """
        module = self._template.module
        macro_fn = getattr(module, name, None)
        if macro_fn is None:
            raise AttributeError(f"Macro '{name}' not found in template")
        return macro_fn

    def get_undeclared_variables(self) -> set[str]:
        """Get undeclared variables from the template AST.

        Returns:
            Set of variable names used in the template.
        """
        source: str | None = None

        # First, try to use stored source (from comment marker transformation)
        if self._source:
            source = self._source
        else:
            # Fall back to loading from template loader
            template_name = self._template.name
            if self._env.loader and template_name:
                source = self._env.loader.get_source(self._env, template_name)[0]

        if not source:
            # For templates from string without stored source,
            # we can't easily get source from compiled template
            return set()

        ast = self._env.parse(source)
        return meta.find_undeclared_variables(ast)

    def assert_variables_subset_of(self, allowed: set[str]) -> None:
        """Assert that all template variables are in the allowed set.

        Useful for CI guardrails to catch templates using unexpected variables.

        Args:
            allowed: Set of allowed variable names.

        Raises:
            UndeclaredVariableError: If template uses variables not in allowed set.
        """
        used = self.get_undeclared_variables()
        # Filter out built-in globals like 'range', 'dict', etc.
        used = {v for v in used if v not in self._env.globals}

        if not used.issubset(allowed):
            raise UndeclaredVariableError(used, allowed)
