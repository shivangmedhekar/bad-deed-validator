"""County resolution and deed enrichment."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from difflib import get_close_matches
from typing import Tuple

from .exceptions import CountyNotFoundError
from .models import DeedData, EnrichedDeedData
from .utils import normalize_county

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# County resolver
# ---------------------------------------------------------------------------

class CountyResolver:
    """Loads a county reference file and resolves raw names via fuzzy matching."""

    def __init__(self, counties_path: str = "counties.json") -> None:
        self._counties = self._load(counties_path)

    @staticmethod
    def _load(path: str) -> list[dict]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def resolve(self, county_raw: str) -> Tuple[str, float]:
        """Return ``(canonical_name, tax_rate)`` for *county_raw*."""
        target = normalize_county(county_raw)
        names = [c["name"] for c in self._counties]
        normalized = [normalize_county(n) for n in names]
        matches = get_close_matches(target, normalized, n=1, cutoff=0.8)

        if not matches:
            raise CountyNotFoundError(f"County not found: {county_raw}")

        idx = normalized.index(matches[0])
        county = self._counties[idx]
        return county["name"], float(county["tax_rate"])


# ---------------------------------------------------------------------------
# Enricher
# ---------------------------------------------------------------------------

class DeedEnricher:
    """Adds county-resolved fields and estimated transfer tax to a deed."""

    def __init__(self, counties_path: str = "counties.json") -> None:
        self._resolver = CountyResolver(counties_path)

    def enrich(self, deed: DeedData) -> EnrichedDeedData:
        logger.info("Starting enrichment for county=%s", deed.county_raw)
        county_name, tax_rate = self._resolver.resolve(deed.county_raw)
        est_tax = int(round(deed.amount_numeric * tax_rate))
        return EnrichedDeedData(
            **asdict(deed),
            county_canonical=county_name,
            tax_rate=tax_rate,
            est_transfer_tax=est_tax,
        )

