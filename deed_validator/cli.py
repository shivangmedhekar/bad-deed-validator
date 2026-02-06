"""Command-line entry point for the deed validator."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, replace
from pathlib import Path

from .config import AppConfig, RAW_DEED_TEXT
from .exceptions import DeedValidationError
from .pipeline import DeedPipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a deed record.")
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        help="Path to OCR/plaintext deed input. Defaults to bundled sample.",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Override OpenAI model (env OPENAI_MODEL is the fallback).",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        type=str,
        help="OpenAI API key override (env OPENAI_API_KEY is the fallback).",
    )
    return parser.parse_args()


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    args = _parse_args()
    config = AppConfig.from_env()

    # Allow CLI overrides for LLM model and API key without mutating env
    if args.model or args.api_key:
        config = replace(
            config,
            llm=replace(
                config.llm,
                model=args.model or config.llm.model,
                api_key=args.api_key or config.llm.api_key,
            ),
        )

    setup_logging(config.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Validator started")

    try:
        pipeline = DeedPipeline(config)
        raw_text = RAW_DEED_TEXT
        if args.input:
            raw_text = args.input.read_text(encoding="utf-8")

        enriched, method = pipeline.process(raw_text)

        print(json.dumps(asdict(enriched), indent=2, default=str))
        print(f"[OK] Extracted by {method}")
    except DeedValidationError as e:
        print(f"[REJECTED] {e}")
        logger.error("Validation failed: %s", e)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
