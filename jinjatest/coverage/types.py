"""
Type definitions for the coverage module.

This module provides type literals and Pydantic models for improved type safety.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, BeforeValidator, Field

ReportType = Literal["term", "term-missing", "term-verbose", "json", "html", "xml"]

BranchType = Literal[
    "if_true",
    "if_false",
    "elif_true",
    "elif_false",
    "for_body",
    "for_else",
    "macro",
    "include",
    "block",
    "cond_true",
    "cond_false",
]

_VALID_REPORT_TYPES: frozenset[str] = frozenset(get_args(ReportType))


def _normalize_and_validate_report_type(value: Any) -> ReportType:
    """Normalize and validate a single report type value.

    Args:
        value: The report type value to validate.

    Returns:
        The normalized report type.

    Raises:
        ValueError: If the value is not a valid report type.
    """
    if not isinstance(value, str):
        raise ValueError(f"Report type must be a string, got {type(value).__name__}")
    normalized = value.lower()
    if normalized not in _VALID_REPORT_TYPES:
        valid_list = ", ".join(sorted(_VALID_REPORT_TYPES))
        raise ValueError(
            f"Invalid report type '{value}'. Valid types are: {valid_list}"
        )
    return normalized


def _normalize_report_type_list(value: Any) -> list[ReportType]:
    """Normalize and validate a list of report types.

    Args:
        value: The list of report types to validate.

    Returns:
        List of normalized report types.

    Raises:
        ValueError: If any value is not a valid report type.
    """
    if not isinstance(value, list):
        raise ValueError(f"Report types must be a list, got {type(value).__name__}")
    return [_normalize_and_validate_report_type(v) for v in value]


ValidatedReportTypeList = Annotated[
    list[ReportType],
    BeforeValidator(_normalize_report_type_list),
]


class CoverageConfig(BaseModel):
    """Configuration for coverage collection from pyproject.toml."""

    enabled: bool = False
    fail_under: float = Field(default=0.0, ge=0.0, le=100.0)
    report: ValidatedReportTypeList = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    html_dir: str = "jt-htmlcov"
    json_file: str = "jt-coverage.json"
    xml_file: str = "jt-coverage.xml"

    model_config = {"extra": "ignore"}
