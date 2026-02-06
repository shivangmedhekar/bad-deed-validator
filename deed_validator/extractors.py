"""Deed field extraction strategies (LLM and regex fallback)."""

from __future__ import annotations

import abc
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from .config import LLMConfig
from .exceptions import LLMExtractionError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keys every extractor must produce
# ---------------------------------------------------------------------------
REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "doc",
        "county",
        "state",
        "date_signed",
        "date_recorded",
        "grantor",
        "grantee",
        "amount_numeric",
        "amount_words",
        "apn",
        "status",
    }
)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class BaseExtractor(abc.ABC):
    """Interface every extraction strategy must implement."""

    @abc.abstractmethod
    def extract(self, raw_text: str) -> Dict[str, Any]:
        """Return a dict with all ``REQUIRED_KEYS`` populated."""


# ---------------------------------------------------------------------------
# LLM-backed extractor
# ---------------------------------------------------------------------------
class LLMExtractor(BaseExtractor):
    """Extracts deed fields by calling an OpenAI model."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._config = config or LLMConfig.from_env()

    # ------------------------------------------------------------------
    def extract(self, raw_text: str) -> Dict[str, Any]:
        logger.info("LLM extraction invoked")

        # Lazy import so the module is test-patchable
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise LLMExtractionError(
                "OpenAI SDK not installed. Run: pip install -r requirements.txt"
            ) from e

        cfg = self._config
        if not cfg.api_key:
            raise LLMExtractionError("OPENAI_API_KEY is not set in environment.")

        client = OpenAI(api_key=cfg.api_key)
        data = self._call_with_retries(client, raw_text, cfg)
        self._validate_keys(data)
        return data

    # ------------------------------------------------------------------
    def _call_with_retries(
        self,
        client: Any,
        raw_text: str,
        cfg: LLMConfig,
    ) -> Dict[str, Any]:
        system_msg = (
            "You extract deed fields from OCR text. "
            "Return ONLY valid JSON with the exact keys requested. No extra keys."
        )
        user_msg = (
            "Extract the following fields from the OCR text.\n\n"
            "Return JSON with keys:\n"
            "doc, county, state, date_signed, date_recorded, grantor, grantee, "
            "amount_numeric, amount_words, apn, status\n\n"
            "Rules:\n"
            "- date_* must be YYYY-MM-DD\n"
            "- amount_numeric must be the string as seen in digits "
            '(e.g. "$1,250,000.00")\n'
            "- amount_words must be the words inside parentheses "
            "(without parentheses)\n\n"
            f"OCR TEXT:\n{raw_text}"
        )

        last_err: Optional[Exception] = None
        for attempt in range(1, cfg.max_retries + 1):
            try:
                logger.info(
                    "LLM request attempt %s/%s using model=%s",
                    attempt,
                    cfg.max_retries,
                    cfg.model,
                )
                resp = client.responses.create(
                    model=cfg.model,
                    input=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    text={"format": {"type": "json_object"}},
                )
                data: Dict[str, Any] = json.loads(resp.output_text)
                logger.info("LLM extraction succeeded on attempt %s", attempt)
                return data
            except Exception as e:
                last_err = e
                logger.warning(
                    "LLM extraction failed on attempt %s/%s: %s",
                    attempt,
                    cfg.max_retries,
                    e,
                )
                if attempt < cfg.max_retries:
                    time.sleep(cfg.retry_delay)

        raise LLMExtractionError(
            f"LLM extraction failed after {cfg.max_retries} attempts: {last_err}"
        ) from last_err

    # ------------------------------------------------------------------
    @staticmethod
    def _validate_keys(data: Dict[str, Any]) -> None:
        missing = REQUIRED_KEYS - set(data.keys())
        extra = set(data.keys()) - REQUIRED_KEYS
        if missing or extra:
            raise LLMExtractionError(
                f"LLM JSON keys invalid. Missing={missing}, Extra={extra}"
            )


# ---------------------------------------------------------------------------
# Regex-based extractor (deterministic fallback)
# ---------------------------------------------------------------------------
class RegexExtractor(BaseExtractor):
    """Extracts deed fields with regular expressions (no network needed)."""

    def extract(self, raw_text: str) -> Dict[str, Any]:
        logger.info("Regex fallback extraction invoked")

        amount_line = self._grab(r"Amount:\s*([^\n]+)", raw_text)
        m_amt = re.search(r"(\$[0-9,]+(?:\.\d{2})?)\s*\((.+?)\)", amount_line)
        if not m_amt:
            raise LLMExtractionError("Regex could not parse amount line.")
        amt_num = m_amt.group(1).strip()
        amt_words = m_amt.group(2).strip()

        mcs = re.search(
            r"County:\s*([^\|]+)\|\s*State:\s*([A-Z]{2})",
            raw_text,
            re.IGNORECASE,
        )
        if not mcs:
            raise LLMExtractionError("Regex could not parse county/state line.")

        data = {
            "doc": self._grab(r"Doc:\s*([A-Z0-9\-\_]+)", raw_text),
            "county": mcs.group(1).strip(),
            "state": mcs.group(2).strip(),
            "date_signed": self._grab(
                r"Date Signed:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", raw_text
            ),
            "date_recorded": self._grab(
                r"Date Recorded:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", raw_text
            ),
            "grantor": self._grab(r"Grantor:\s*(.+)", raw_text),
            "grantee": self._grab(r"Grantee:\s*(.+)", raw_text),
            "amount_numeric": amt_num,
            "amount_words": amt_words,
            "apn": self._grab(r"APN:\s*([A-Z0-9\-]+)", raw_text),
            "status": self._grab(r"Status:\s*([A-Z]+)", raw_text),
        }
        logger.info("Regex extraction succeeded")
        return data

    # ------------------------------------------------------------------
    @staticmethod
    def _grab(pattern: str, text: str) -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            raise LLMExtractionError(
                f"Regex extraction failed for pattern: {pattern}"
            )
        return m.group(1).strip()

