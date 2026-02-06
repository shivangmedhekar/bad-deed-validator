"""Orchestrates the full deed processing pipeline.

    extract → build → validate → enrich
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from .config import AppConfig
from .enrichment import DeedEnricher
from .exceptions import DeedValidationError
from .extractors import BaseExtractor, LLMExtractor, RegexExtractor
from .models import DeedData, EnrichedDeedData
from .utils import dollars_to_int, parse_iso_date
from .validators import DeedValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Builder (dict → typed dataclass)
# ---------------------------------------------------------------------------

class DeedBuilder:
    """Converts a raw extraction dict into a typed :class:`DeedData`."""

    @staticmethod
    def build(llm_obj: Dict[str, Any]) -> DeedData:
        logger.info("Building typed deed data")
        return DeedData(
            doc=str(llm_obj["doc"]).strip(),
            county_raw=str(llm_obj["county"]).strip(),
            state=str(llm_obj["state"]).strip(),
            date_signed=parse_iso_date(str(llm_obj["date_signed"])),
            date_recorded=parse_iso_date(str(llm_obj["date_recorded"])),
            grantor=str(llm_obj["grantor"]).strip(),
            grantee=str(llm_obj["grantee"]).strip(),
            amount_numeric=dollars_to_int(str(llm_obj["amount_numeric"])),
            amount_words=str(llm_obj["amount_words"]).strip(),
            apn=str(llm_obj["apn"]).strip(),
            status=str(llm_obj["status"]).strip(),
        )


# ---------------------------------------------------------------------------
# Pipeline (end-to-end orchestrator)
# ---------------------------------------------------------------------------

class DeedPipeline:
    """High-level façade: feed in raw OCR text, get an enriched deed out.

    Tries the LLM extractor first, then falls back to regex.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or AppConfig.from_env()
        self._llm_extractor: BaseExtractor = LLMExtractor(self._config.llm)
        self._regex_extractor: BaseExtractor = RegexExtractor()
        self._builder = DeedBuilder()
        self._validator = DeedValidator()
        self._enricher = DeedEnricher(self._config.counties_path)

    # ------------------------------------------------------------------
    def process(self, raw_text: str) -> Tuple[EnrichedDeedData, str]:
        """Return ``(enriched_deed, extraction_method)``."""
        llm_obj, method = self._extract(raw_text)
        deed = self._builder.build(llm_obj)
        logger.info("Document parsed: doc=%s", deed.doc)

        self._validator.validate(deed)
        enriched = self._enricher.enrich(deed)

        logger.info("Processing completed successfully with method=%s", method)
        return enriched, method

    # ------------------------------------------------------------------
    def _extract(self, raw_text: str) -> Tuple[Dict[str, Any], str]:
        try:
            return self._llm_extractor.extract(raw_text), "llm"
        except Exception as exc:
            logger.warning("LLM extraction failed: %s", exc)
            result = self._regex_extractor.extract(raw_text)
            logger.info("Fallback extraction method used: regex")
            return result, "regex"

