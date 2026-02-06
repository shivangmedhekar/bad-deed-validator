"""Utility functions for parsing, conversion, and normalization."""

from __future__ import annotations

import re
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_iso_date(s: str) -> date:
    """Parse a ``YYYY-MM-DD`` string into a :class:`datetime.date`."""
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Dollar-amount helpers
# ---------------------------------------------------------------------------

def dollars_to_int(amount_str: str) -> int:
    """Convert ``'$1,250,000.00'`` → ``1250000`` (int dollars, cents ignored)."""
    s = amount_str.strip().replace("$", "").replace(",", "")
    m = re.fullmatch(r"(\d+)(?:\.(\d{1,2}))?", s)
    if not m:
        raise ValueError(f"Invalid numeric amount: {amount_str}")
    return int(m.group(1))


_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_SCALES: dict[str, int] = {
    "hundred": 100,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}


def words_to_int(words: str) -> int:
    """Convert ``'One Million Two Hundred Thousand Dollars'`` → ``1_200_000``."""
    s = words.lower()
    s = re.sub(r"[^a-z\s-]", " ", s)
    s = s.replace("-", " ")
    tokens = [t for t in s.split() if t not in {"and", "dollar", "dollars"}]

    if not tokens:
        raise ValueError(f"Empty amount words: {words}")

    total = 0
    current = 0
    for t in tokens:
        if t in _WORDS:
            current += _WORDS[t]
        elif t == "hundred":
            if current == 0:
                current = 1
            current *= 100
        elif t in ("thousand", "million", "billion"):
            scale = _SCALES[t]
            if current == 0:
                current = 1
            total += current * scale
            current = 0
        else:
            raise ValueError(f"Unrecognized number word '{t}' in: {words}")

    return total + current


# ---------------------------------------------------------------------------
# County normalization
# ---------------------------------------------------------------------------

def normalize_county(county_raw: str) -> str:
    """Normalize a raw county name for fuzzy matching."""
    s = county_raw.strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.replace("s clara", "santa clara")
    s = s.replace("st clara", "santa clara")
    s = s.replace("st ", "saint ")
    return s

