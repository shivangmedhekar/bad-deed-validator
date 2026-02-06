"""Centralized configuration, constants, and sample data."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Configuration data-classes (immutable, built from environment)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMConfig:
    """Settings for the OpenAI-backed extractor."""

    api_key: str
    model: str
    max_retries: int
    retry_delay: float

    @classmethod
    def from_env(cls) -> LLMConfig:
        load_dotenv()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
            retry_delay=float(os.getenv("LLM_RETRY_DELAY", "1.0")),
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    log_level: str
    counties_path: str
    llm: LLMConfig

    @classmethod
    def from_env(cls) -> AppConfig:
        load_dotenv()
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            counties_path=os.getenv("COUNTIES_PATH", "counties.json"),
            llm=LLMConfig.from_env(),
        )


# ---------------------------------------------------------------------------
# Sample input (kept for CLI demo & tests)
# ---------------------------------------------------------------------------

RAW_DEED_TEXT = """*** RECORDING REQ ***
Doc: DEED-TRUST-0042
County: S. Clara  |  State: CA
Date Signed: 2024-01-15
Date Recorded: 2024-01-10
Grantor:  T.E.S.L.A. Holdings LLC
Grantee:  John  &  Sarah  Connor
Amount: $1,250,000.00 (One Million Two Hundred Thousand Dollars)
APN: 992-001-XA
Status: PRELIMINARY
*** END ***"""

