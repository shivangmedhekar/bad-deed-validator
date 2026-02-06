"""Data models for deed records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DeedData:
    """Raw parsed deed fields."""

    doc: str
    county_raw: str
    state: str
    date_signed: date
    date_recorded: date
    grantor: str
    grantee: str
    amount_numeric: int
    amount_words: str
    apn: str
    status: str


@dataclass(frozen=True)
class EnrichedDeedData(DeedData):
    """DeedData augmented with county resolution and tax estimates."""

    county_canonical: str
    tax_rate: float
    est_transfer_tax: int

