import json
import os
import sys
import types

import pytest

from deed_validator import (
    RAW_DEED_TEXT,
    AmountMismatchError,
    CountyNotFoundError,
    DateOrderError,
    LLMExtractionError,
    build_deed_data,
    enrich,
    extract_with_llm,
    extract_with_regex,
    sanity_checks,
    DeedValidationError,
)


def test_rejects_bad_deed_with_both_errors():
    llm_obj = extract_with_regex(RAW_DEED_TEXT)
    deed = build_deed_data(llm_obj)

    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)

    msg = str(excinfo.value)
    assert "recorded 2024-01-10 is before signed 2024-01-15" in msg
    assert "Amount mismatch: numeric=1,250,000 vs words=1,200,000" in msg


def build_deed_from_text(raw_text: str):
    llm_obj = extract_with_regex(raw_text)
    return build_deed_data(llm_obj)


def test_valid_deed_passes_sanity_checks():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-0043
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  ABC Properties LLC
Grantee:  Jane Doe
Amount: $500,000.00 (Five Hundred Thousand Dollars)
APN: 992-002-XB
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    # should not raise
    sanity_checks(deed)


def test_date_order_error_only():
    text = """*** RECORDING REQ ***
Doc: DT-2024-FAIL-DATE
County: Santa Clara  |  State: CA
Date Signed: 2024-02-10
Date Recorded: 2024-02-05
Grantor:  Bad Date LLC
Grantee:  Test User
Amount: $300,000.00 (Three Hundred Thousand Dollars)
APN: 771-004-YD
Status: PRELIMINARY
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    msg = str(excinfo.value)
    assert "Invalid dates" in msg
    assert "2024-02-05" in msg
    assert "2024-02-10" in msg


def test_amount_mismatch_only():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-0046
County: S. Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Mismatch LLC
Grantee:  Careful Buyer
Amount: $800,000.00 (One Million Dollars)
APN: 992-005-WE
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    msg = str(excinfo.value)
    assert "Amount mismatch" in msg
    assert "800,000" in msg
    assert "1,000,000" in msg


def test_bad_date_format_triggers_extraction_error():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-0045
County: Santa Cruz  |  State: CA
Date Signed: 01/32/2024
Date Recorded: 2024-02-15
Grantor:  Bad Date LLC
Grantee:  Test User
Amount: $300,000.00 (Three Hundred Thousand Dollars)
APN: 771-004-YD
Status: PRELIMINARY
*** END ***"""
    with pytest.raises(LLMExtractionError):
        build_deed_from_text(text)


def test_missing_amount_words_rejected_by_regex():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-0047
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Incomplete Data LLC
Grantee:  Risk Taker
Amount: $600,000.00
APN: 992-006-VF
Status: PRELIMINARY
*** END ***"""
    with pytest.raises(LLMExtractionError):
        build_deed_from_text(text)


def test_county_normalization_and_tax_rate():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-CLARA
County: S. Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  County Match LLC
Grantee:  Buyer
Amount: $1,000,000.00 (One Million Dollars)
APN: 992-100-XY
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical == "Santa Clara"
    assert enriched.tax_rate == 0.012


def test_unknown_county_raises():
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-UNKNOWN
County: Los Angeles  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  LA LLC
Grantee:  Buyer
Amount: $400,000.00 (Four Hundred Thousand Dollars)
APN: 992-200-XZ
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(CountyNotFoundError):
        enrich(deed)


# ============================================================================
# NEW TEST CASES - Date Validation
# ============================================================================

def test_same_date_signed_and_recorded():
    """Same date for signing and recording should be valid"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-SAME-DATE
County: Santa Clara  |  State: CA
Date Signed: 2024-01-15
Date Recorded: 2024-01-15
Grantor:  Same Day LLC
Grantee:  Quick Buyer
Amount: $750,000.00 (Seven Hundred Fifty Thousand Dollars)
APN: 881-003-ZC
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)


def test_large_time_gap_valid():
    """Valid case with large time gap (6 months)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-DELAY
County: San Mateo  |  State: CA
Date Signed: 2024-01-01
Date Recorded: 2024-06-30
Grantor:  Delayed Recording LLC
Grantee:  Patient Buyer
Amount: $2,000,000.00 (Two Million Dollars)
APN: 882-004-AA
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)


def test_dates_across_year_boundary():
    """Dates spanning year end"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-YEAR-END
County: Santa Cruz  |  State: CA
Date Signed: 2023-12-28
Date Recorded: 2024-01-05
Grantor:  Year End LLC
Grantee:  New Year Buyer
Amount: $900,000.00 (Nine Hundred Thousand Dollars)
APN: 773-005-BB
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)


def test_one_day_difference_invalid():
    """Recorded one day before signed"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-ONE-DAY
County: Santa Clara  |  State: CA
Date Signed: 2024-01-16
Date Recorded: 2024-01-15
Grantor:  One Day Off LLC
Grantee:  Confused Buyer
Amount: $450,000.00 (Four Hundred Fifty Thousand Dollars)
APN: 992-030-ZZ
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    assert "Invalid dates" in str(excinfo.value)


def test_many_months_apart_invalid():
    """Recorded 6 months before signed (impossible)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-TIME-TRAVEL
County: Santa Clara  |  State: CA
Date Signed: 2024-06-01
Date Recorded: 2024-01-01
Grantor:  Time Traveler LLC
Grantee:  Future Buyer
Amount: $525,000.00 (Five Hundred Twenty Five Thousand Dollars)
APN: 992-031-AA
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    assert "Invalid dates" in str(excinfo.value)


# ============================================================================
# NEW TEST CASES - Amount Validation
# ============================================================================

def test_zero_dollar_amount():
    """Zero dollar transaction (gift deed)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-GIFT
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Generous Donor
Grantee:  Lucky Recipient
Amount: $0.00 (Zero Dollars)
APN: 992-011-DD
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)
    assert deed.amount_numeric == 0


def test_very_large_amount():
    """Very large transaction (50 million)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-LARGE
County: San Mateo  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Big Money LLC
Grantee:  Rich Buyer
Amount: $50,000,000.00 (Fifty Million Dollars)
APN: 883-012-EE
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)
    assert deed.amount_numeric == 50_000_000


def test_amount_off_by_one_dollar():
    """Small $1 discrepancy should be caught"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-OFF-ONE
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Almost Right LLC
Grantee:  Close Buyer
Amount: $1,000,001.00 (One Million Dollars)
APN: 992-014-GG
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    assert "Amount mismatch" in str(excinfo.value)
    assert "1,000,001" in str(excinfo.value)
    assert "1,000,000" in str(excinfo.value)


def test_amount_off_by_thousand():
    """$1000 discrepancy"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-OFF-THOUSAND
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Slightly Wrong LLC
Grantee:  Unlucky Buyer
Amount: $501,000.00 (Five Hundred Thousand Dollars)
APN: 992-032-BB
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    assert "Amount mismatch" in str(excinfo.value)


def test_amount_hundred_million():
    """Test large round number parsing"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-100M
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Huge Deal LLC
Grantee:  Mega Buyer
Amount: $100,000,000.00 (One Hundred Million Dollars)
APN: 992-033-CC
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)
    assert deed.amount_numeric == 100_000_000


def test_amount_with_and_word():
    """Amount words with 'and' (legal format)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-AND
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Proper Format LLC
Grantee:  Legal Buyer
Amount: $1,500,000.00 (One Million and Five Hundred Thousand Dollars)
APN: 992-013-FF
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)


def test_amount_complex_number():
    """Complex amount with hundreds and thousands"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-COMPLEX
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Complex LLC
Grantee:  Detail Buyer
Amount: $3,456,789.00 (Three Million Four Hundred Fifty Six Thousand Seven Hundred Eighty Nine Dollars)
APN: 992-034-DD
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    sanity_checks(deed)
    assert deed.amount_numeric == 3_456_789


# ============================================================================
# NEW TEST CASES - County Matching
# ============================================================================

def test_county_all_uppercase():
    """County in all caps"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-CAPS
County: SANTA CLARA  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Caps LLC
Grantee:  Loud Buyer
Amount: $600,000.00 (Six Hundred Thousand Dollars)
APN: 992-015-HH
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical == "Santa Clara"
    assert enriched.tax_rate == 0.012


def test_county_all_lowercase():
    """County in lowercase"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-LOWER
County: santa clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Lower LLC
Grantee:  Quiet Buyer
Amount: $700,000.00 (Seven Hundred Thousand Dollars)
APN: 992-016-II
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical == "Santa Clara"


def test_county_extra_spaces():
    """County with extra whitespace"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-SPACE
County:   Santa   Clara   |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Spacey LLC
Grantee:  Spaced Buyer
Amount: $800,000.00 (Eight Hundred Thousand Dollars)
APN: 992-017-JJ
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical == "Santa Clara"


def test_county_abbreviation_st():
    """Different abbreviation (St. instead of S.)"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-ST
County: St. Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Alternate LLC
Grantee:  Different Buyer
Amount: $550,000.00 (Five Hundred Fifty Thousand Dollars)
APN: 992-035-EE
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical in ["Santa Clara", "Saint Clara"]


def test_all_three_counties():
    """Test each county from counties.json"""
    counties_tests = [
        ("Santa Clara", 0.012),
        ("San Mateo", 0.011),
        ("Santa Cruz", 0.010),
    ]

    for county_name, expected_rate in counties_tests:
        text = f"""*** RECORDING REQ ***
Doc: DEED-TRUST-{county_name.replace(' ', '-').upper()}
County: {county_name}  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  County Test LLC
Grantee:  Tax Buyer
Amount: $1,000,000.00 (One Million Dollars)
APN: 992-036-FF
Status: FINAL
*** END ***"""
        deed = build_deed_from_text(text)
        enriched = enrich(deed)
        assert enriched.county_canonical == county_name
        assert enriched.tax_rate == expected_rate


def test_san_mateo_abbreviated():
    """San Mateo with abbreviation"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-SM
County: S. Mateo  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Mateo LLC
Grantee:  Bay Buyer
Amount: $1,200,000.00 (One Million Two Hundred Thousand Dollars)
APN: 884-037-GG
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.county_canonical == "San Mateo"
    assert enriched.tax_rate == 0.011


# ============================================================================
# NEW TEST CASES - Tax Calculation
# ============================================================================

def test_tax_calculation_santa_clara():
    """Verify tax calculation for Santa Clara"""
    text = """*** RECORDING REQ ***
Doc: DEED-TAX-SC
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Tax Test LLC
Grantee:  Math Buyer
Amount: $1,000,000.00 (One Million Dollars)
APN: 992-038-HH
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.est_transfer_tax == 12_000  # 1M * 0.012


def test_tax_calculation_san_mateo():
    """Verify tax calculation for San Mateo"""
    text = """*** RECORDING REQ ***
Doc: DEED-TAX-SM
County: San Mateo  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Tax Test LLC
Grantee:  Math Buyer
Amount: $2,000,000.00 (Two Million Dollars)
APN: 884-039-II
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.est_transfer_tax == 22_000  # 2M * 0.011


def test_tax_calculation_santa_cruz():
    """Verify tax calculation for Santa Cruz"""
    text = """*** RECORDING REQ ***
Doc: DEED-TAX-SZ
County: Santa Cruz  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Tax Test LLC
Grantee:  Math Buyer
Amount: $500,000.00 (Five Hundred Thousand Dollars)
APN: 773-040-JJ
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    enriched = enrich(deed)
    assert enriched.est_transfer_tax == 5_000  # 500K * 0.010


# ============================================================================
# NEW TEST CASES - Multiple Errors
# ============================================================================

def test_both_date_and_amount_errors():
    """Document with both errors"""
    text = """*** RECORDING REQ ***
Doc: DEED-TRUST-DOUBLE-ERROR
County: Santa Clara  |  State: CA
Date Signed: 2024-01-20
Date Recorded: 2024-01-15
Grantor:  Double Error LLC
Grantee:  Unlucky Buyer
Amount: $1,500,000.00 (One Million Dollars)
APN: 992-041-KK
Status: PRELIMINARY
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)
    error_msg = str(excinfo.value)
    assert "Invalid dates" in error_msg or "2024-01-15" in error_msg
    assert "Amount mismatch" in error_msg or "1,500,000" in error_msg


# ============================================================================
# NEW TEST CASES - Edge Cases
# ============================================================================

def test_apn_with_letters():
    """APN with letters at the end"""
    text = """*** RECORDING REQ ***
Doc: DEED-APN-LETTERS
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  APN Test LLC
Grantee:  Format Buyer
Amount: $400,000.00 (Four Hundred Thousand Dollars)
APN: 992-001-XA
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    assert deed.apn == "992-001-XA"


def test_status_case_variations():
    """Test different status cases"""
    for status in ["FINAL", "PRELIMINARY"]:
        text = f"""*** RECORDING REQ ***
Doc: DEED-STATUS-{status}
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Status LLC
Grantee:  State Buyer
Amount: $500,000.00 (Five Hundred Thousand Dollars)
APN: 992-042-LL
Status: {status}
*** END ***"""
        deed = build_deed_from_text(text)
        assert deed.status == status


def test_grantor_with_periods_and_ampersand():
    """Grantor with complex name"""
    text = """*** RECORDING REQ ***
Doc: DEED-COMPLEX-NAME
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  T.E.S.L.A. Holdings LLC
Grantee:  Simple Buyer
Amount: $1,100,000.00 (One Million One Hundred Thousand Dollars)
APN: 992-043-MM
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    assert "T.E.S.L.A." in deed.grantor or "TESLA" in deed.grantor


def test_grantee_with_ampersand():
    """Multiple grantees with ampersand"""
    text = """*** RECORDING REQ ***
Doc: DEED-MULTI-GRANTEE
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Single Seller LLC
Grantee:  John  &  Sarah  Connor
Amount: $875,000.00 (Eight Hundred Seventy Five Thousand Dollars)
APN: 992-044-NN
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    assert "&" in deed.grantee or "and" in deed.grantee.lower()


# ============================================================================
# NEW TEST CASES - Integration/End-to-End
# ============================================================================

def test_perfect_document_end_to_end():
    """Complete valid document - full workflow"""
    text = """*** RECORDING REQ ***
Doc: DEED-PERFECT-E2E
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Perfect Properties LLC
Grantee:  Happy Home Buyer
Amount: $1,000,000.00 (One Million Dollars)
APN: 992-999-XX
Status: FINAL
*** END ***"""

    llm_obj = extract_with_regex(text)
    deed = build_deed_data(llm_obj)
    sanity_checks(deed)
    enriched = enrich(deed)
    assert enriched.county_canonical == "Santa Clara"
    assert enriched.tax_rate == 0.012
    assert enriched.est_transfer_tax == 12_000


def test_amount_parsing_edge_cases():
    """Test words_to_int with various formats"""
    from deed_validator import words_to_int

    test_cases = [
        ("One Million Dollars", 1_000_000),
        ("Five Hundred Thousand Dollars", 500_000),
        ("Two Million Five Hundred Thousand Dollars", 2_500_000),
        ("Three Hundred Thousand Dollars", 300_000),
        ("Fifty Thousand Dollars", 50_000),
        ("Nine Hundred Ninety Nine Thousand Nine Hundred Ninety Nine Dollars", 999_999),
        ("One Hundred Million Dollars", 100_000_000),
        ("Zero Dollars", 0),
    ]

    for words, expected in test_cases:
        result = words_to_int(words)
        assert result == expected, f"Failed for '{words}': got {result}, expected {expected}"


# ============================================================================
# NEW TEST CASES - Error Message Quality
# ============================================================================

def test_error_message_quality_date():
    """Verify date error has clear message"""
    text = """*** RECORDING REQ ***
Doc: DEED-ERROR-DATE
County: Santa Clara  |  State: CA
Date Signed: 2024-03-15
Date Recorded: 2024-03-10
Grantor:  Error LLC
Grantee:  Test Buyer
Amount: $500,000.00 (Five Hundred Thousand Dollars)
APN: 992-045-OO
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)

    error_msg = str(excinfo.value)
    assert "2024-03-10" in error_msg
    assert "2024-03-15" in error_msg
    assert "recorded" in error_msg.lower()
    assert "signed" in error_msg.lower()


def test_error_message_quality_amount():
    """Verify amount error has clear message"""
    text = """*** RECORDING REQ ***
Doc: DEED-ERROR-AMT
County: Santa Clara  |  State: CA
Date Signed: 2024-01-10
Date Recorded: 2024-01-15
Grantor:  Amount LLC
Grantee:  Number Buyer
Amount: $750,000.00 (Seven Hundred Thousand Dollars)
APN: 992-046-PP
Status: FINAL
*** END ***"""
    deed = build_deed_from_text(text)
    with pytest.raises(DeedValidationError) as excinfo:
        sanity_checks(deed)

    error_msg = str(excinfo.value)
    assert "750,000" in error_msg or "750000" in error_msg
    assert "700,000" in error_msg or "700000" in error_msg
    assert "mismatch" in error_msg.lower()

def test_extract_with_llm_uses_openai(monkeypatch):
    # Arrange a fake OpenAI module that records calls and returns deterministic JSON
    fake_payload = {
        "doc": "LLM-TEST-001",
        "county": "Santa Clara",
        "state": "CA",
        "date_signed": "2024-01-10",
        "date_recorded": "2024-01-15",
        "grantor": "LLM Grantor",
        "grantee": "LLM Grantee",
        "amount_numeric": "$1,000,000.00",
        "amount_words": "One Million Dollars",
        "apn": "999-999-LLM",
        "status": "FINAL",
    }

    calls = []

    class DummyResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(output_text=json.dumps(fake_payload))

    class DummyClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = DummyResponses()

    dummy_module = types.SimpleNamespace(OpenAI=DummyClient)
    monkeypatch.setitem(sys.modules, "openai", dummy_module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    result = extract_with_llm(RAW_DEED_TEXT)

    assert result["doc"] == "LLM-TEST-001"
    assert calls, "LLM client should have been invoked"
    assert calls[0]["model"] == "test-model"


@pytest.mark.integration
def test_extract_with_llm_real_call():
    """Optional real call; runs only when env is configured."""
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("RUN_REAL_LLM"):
        pytest.skip("Set OPENAI_API_KEY and RUN_REAL_LLM=1 to run real LLM integration test.")

    llm_obj = extract_with_llm(RAW_DEED_TEXT)
    # Should contain required keys and be buildable
    for key in ("doc", "county", "state", "date_signed", "date_recorded", "grantor", "grantee", "amount_numeric", "amount_words", "apn", "status"):
        assert key in llm_obj

    deed = build_deed_data(llm_obj)
    # The sample text is intentionally bad, so validation should still fail closed
    with pytest.raises(DeedValidationError):
        sanity_checks(deed)
