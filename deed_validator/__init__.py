"""deed_validator – structured deed validation package.

Public API
==========
This ``__init__`` re-exports every symbol that external code (including the
test suite) previously imported from the old monolithic ``deed_validator.py``.
It also exposes the new OOP classes for consumers who prefer them.
"""

from __future__ import annotations

# --- Constants & sample data ------------------------------------------------
from .config import RAW_DEED_TEXT, AppConfig, LLMConfig

# --- Exception hierarchy ----------------------------------------------------
from .exceptions import (
    AmountMismatchError,
    CountyNotFoundError,
    DateOrderError,
    DeedValidationError,
    LLMExtractionError,
)

# --- Data models ------------------------------------------------------------
from .models import DeedData, EnrichedDeedData

# --- Utilities (exposed for direct use / tests) -----------------------------
from .utils import dollars_to_int, normalize_county, parse_iso_date, words_to_int

# --- OOP classes ------------------------------------------------------------
from .extractors import BaseExtractor, LLMExtractor, RegexExtractor
from .validators import DeedValidator
from .enrichment import CountyResolver, DeedEnricher
from .pipeline import DeedBuilder, DeedPipeline

# --- CLI entry-point --------------------------------------------------------
from .cli import main, setup_logging

# ---------------------------------------------------------------------------
# Backward-compatible free functions
# (thin wrappers that delegate to the OOP classes above)
# ---------------------------------------------------------------------------

_regex_extractor = RegexExtractor()
_validator = DeedValidator()


def extract_with_llm(raw_text: str) -> dict:
    """Extract deed fields using an OpenAI LLM."""
    return LLMExtractor().extract(raw_text)


def extract_with_regex(raw_text: str) -> dict:
    """Extract deed fields using regex (deterministic fallback)."""
    return _regex_extractor.extract(raw_text)


def build_deed_data(llm_obj: dict) -> DeedData:
    """Convert a raw extraction dict into a typed :class:`DeedData`."""
    return DeedBuilder.build(llm_obj)


def sanity_checks(deed: DeedData) -> None:
    """Run validation rules against *deed*; raises on failure."""
    _validator.validate(deed)


def enrich(deed: DeedData, counties_path: str = "counties.json") -> EnrichedDeedData:
    """Resolve county and compute transfer tax."""
    return DeedEnricher(counties_path).enrich(deed)


# ---------------------------------------------------------------------------
__all__ = [
    # Constants
    "RAW_DEED_TEXT",
    # Config
    "AppConfig",
    "LLMConfig",
    # Exceptions
    "AmountMismatchError",
    "CountyNotFoundError",
    "DateOrderError",
    "DeedValidationError",
    "LLMExtractionError",
    # Models
    "DeedData",
    "EnrichedDeedData",
    # Utilities
    "dollars_to_int",
    "normalize_county",
    "parse_iso_date",
    "words_to_int",
    # OOP classes
    "BaseExtractor",
    "LLMExtractor",
    "RegexExtractor",
    "DeedValidator",
    "CountyResolver",
    "DeedEnricher",
    "DeedBuilder",
    "DeedPipeline",
    # Backward-compat functions
    "extract_with_llm",
    "extract_with_regex",
    "build_deed_data",
    "sanity_checks",
    "enrich",
    # CLI
    "main",
    "setup_logging",
]

