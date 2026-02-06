"""Custom exception hierarchy for deed validation."""

from __future__ import annotations


class DeedValidationError(Exception):
    """Base class for deed validation errors."""


class DateOrderError(DeedValidationError):
    """Recorded date earlier than signed date."""


class AmountMismatchError(DeedValidationError):
    """Numeric amount and words amount differ."""


class CountyNotFoundError(DeedValidationError):
    """County could not be resolved."""


class LLMExtractionError(DeedValidationError):
    """LLM extraction failed or produced invalid output."""

