# Bad Deed Validator

A "paranoid" deed-validation pipeline that uses an LLM **only** for
extraction, then applies **deterministic Python code** for every critical
check—ensuring no hallucinated number or impossible date ever slips through.

## Quick Start

### 1) Create & activate a virtual env

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
```

### 2) Install deps and set env vars

```bash
pip install -r requirements.txt
cp .env.example .env   # optional — regex fallback works without an API key
```

### 3) Run the CLI

```bash
python -m deed_validator          # uses built-in sample deed
python -m deed_validator --help   # see options
```

### 4) Run tests

```bash
pytest -v
pytest -k llm --maxfail=1   # runs only LLM-dependent tests when an API key is set
```

## Approach & Design Decisions

### 1. LLM extracts, code validates (never the reverse)

The LLM (`LLMExtractor`) is treated as an **untrusted** data source.  It
parses messy OCR text into a structured JSON object, but every value it
returns is then verified by deterministic rules before the deed is accepted.
If the LLM is unavailable or returns malformed data, a `RegexExtractor`
kicks in as a fully offline fallback.

### 2. Date logic — caught by code, not AI

The recorded-before-signed check is a simple `date` comparison in
`DeedValidator._check_date_order()`.  The LLM is never asked "do these
dates make sense?"; we compare `date_recorded < date_signed` in Python and
raise a `DateOrderError` if it fails.

### 3. Money check — digits vs. words cross-verification

`words_to_int()` is a hand-written English-number parser that converts the
written-out amount to an integer.  `DeedValidator._check_amount_match()`
then compares it against the parsed numeric amount.  A $1 discrepancy is
enough to reject the deed with an `AmountMismatchError`.  Both the numeric
and the word values are shown in the error message so a human reviewer can
see exactly what went wrong.

### 4. "S. Clara" → "Santa Clara" county resolution

A two-layer approach:

1. **Normalization** (`normalize_county()`): expands known abbreviations
   (e.g. `S.` → `Santa`, `St.` → `Saint`), strips punctuation, and
   lowercases.
2. **Fuzzy matching** (`CountyResolver.resolve()`): uses
   `difflib.get_close_matches` with a 0.8 cutoff against the canonical
   names in `counties.json`.  If nothing matches, a `CountyNotFoundError`
   is raised rather than guessing.

### 5. Fail-closed, all-errors-at-once

The validator **collects every violation** before raising, so a reviewer
sees the full picture ("date is wrong AND amount is wrong") in one pass.

## Project Structure

```
deed_validator/          # Main package
├── __init__.py          # Public API & backward-compatible free functions
├── __main__.py          # python -m deed_validator entry point
├── cli.py               # CLI main()
├── config.py            # AppConfig / LLMConfig (from env vars), sample input
├── enrichment.py        # CountyResolver + DeedEnricher
├── exceptions.py        # DeedValidationError hierarchy
├── extractors.py        # BaseExtractor → LLMExtractor, RegexExtractor
├── models.py            # DeedData, EnrichedDeedData (frozen dataclasses)
├── pipeline.py          # DeedBuilder + DeedPipeline orchestrator
├── utils.py             # parse_iso_date, dollars_to_int, words_to_int, normalize_county
└── validators.py        # DeedValidator (deterministic sanity checks)

counties.json            # Reference county data with tax rates
test_deed_validator.py   # 40 pytest cases (39 pass, 1 skipped without API key)
```

## LLM CLI options

- **When you need it:** Only required if you want the `LLMExtractor` to parse OCR‑style deed text. The deterministic validator and regex extractor work without an API key.
- **Prereqs:** Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Optional: set `OPENAI_MODEL` (defaults to `gpt-4.1-mini`).
- **Default behavior:** `python -m deed_validator` always *tries* the LLM first; if `OPENAI_API_KEY` is missing or the call fails, it falls back to the regex extractor and still runs end-to-end (you'll see a warning in logs).

```bash
export OPENAI_API_KEY="sk-..."          # required for LLM path
export OPENAI_MODEL="gpt-4o"            # optional override
python -m deed_validator                # runs with the sample deed
python -m deed_validator --input path/to/your_deed.txt
python -m deed_validator --model gpt-4o-mini   # CLI override instead of env
python -m deed_validator --api-key sk-...      # CLI override instead of env
```

The bundled sample deed is intentionally invalid (bad dates + mismatched amount). With LLM enabled you should still see a rejection, e.g.:

```
[REJECTED] Sanity checks failed:
 - Invalid dates: recorded 2024-01-10 is before signed 2024-01-15.
 - Amount mismatch: numeric=1,250,000 vs words=1,200,000 ...
```
