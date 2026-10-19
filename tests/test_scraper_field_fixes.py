"""
Offline tests for the scraper field fixes found in the field audit: exit load, Gold minimum investment,
full risk label, no placeholder daily change, and N/A flowing through validation and documents.

Fixtures are real INDmoney pages (page.html and the rendered main.txt, saved 2026-10-19) under
tests/fixtures/<fund_id>/. No network. Each case runs two ways: on the saved HTML alone (BeautifulSoup text, what
extract_fund_data uses without a browser page) and on the saved rendered text (what it sees live).
"""

import sys
from pathlib import Path

# tests/fixtures (saved INDmoney pages) is not part of every checkout. Without it this file skips cleanly instead of failing.
if not (Path(__file__).resolve().parent / "fixtures").is_dir():
    _SKIP_REASON = "tests/fixtures (saved INDmoney pages) is not in this checkout"
    if __name__ == "__main__":
        print(f"SKIPPED: {_SKIP_REASON}")
        raise SystemExit(0)
    try:
        import pytest
    except ImportError:
        raise SystemExit(f"SKIPPED: {_SKIP_REASON}")
    pytest.skip(_SKIP_REASON, allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import phase_1.scraper as scraper
from phase_1.documents import record_to_text
from phase_1.validation import validate_fund_record

FIXTURES = Path(__file__).resolve().parent / "fixtures"
IDS = {
    "infra": "hdfc-infrastructure-fund-direct-plan-growth-option-3315",
    "mid": "hdfc-mid-cap-fund-direct-plan-growth-option-3097",
    "small": "hdfc-small-cap-fund-direct-growth-option-3580",
    "flexi": "hdfc-flexi-cap-fund-direct-plan-growth-option-3184",
    "value": "hdfc-value-fund-direct-plan-growth-option-3623",
    "debt": "hdfc-dynamic-debt-plan-direct-plan-growth-option-513",
    "lowdur": "hdfc-low-duration-direct-plan-growth-option-1481",
    "gold": "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359",
    "hybrid": "hdfc-hybrid-equity-fund-direct-growth-option-4103",
    "eqsav": "hdfc-equity-savings-fund-direct-plan-growth-option-4569",
}


def _fixture(key: str, name: str) -> str:
    path = FIXTURES / IDS[key] / name
    if not path.exists():
        raise AssertionError(f"fixture missing: {path} (saved INDmoney pages live in tests/fixtures)")
    return path.read_text()


def extract(key: str, live: bool, edit=None) -> dict:
    """Run extract_fund_data on a saved page. `edit(html, main_text)` may return modified copies."""
    html, main = _fixture(key, "page.html"), _fixture(key, "main.txt")
    if edit:
        html, main = edit(html, main)
    original = scraper._get_text_for_extraction
    if live:
        scraper._get_text_for_extraction = lambda _html, _page: main
    try:
        return scraper.extract_fund_data(html, IDS[key], key, f"https://www.indmoney.com/mutual-funds/{IDS[key]}")
    finally:
        scraper._get_text_for_extraction = original


def both(key: str, edit=None):
    return [extract(key, live, edit) for live in (False, True)]


# 1. exit load -------------------------------------------------------------------------------

def test_exit_load_is_captured_when_the_overview_card_is_the_only_source():
    # Dynamic Debt and Low Duration show "Exit Load 0%" and have no FAQ sentence about it.
    for key in ("debt", "lowdur"):
        for data in both(key):
            assert data["exit_load"] == "0%", (key, data["exit_load"])


def test_exit_load_values_that_were_already_captured_are_unchanged():
    for key in ("infra", "mid", "small", "flexi", "value", "gold", "hybrid", "eqsav"):
        for data in both(key):
            assert data["exit_load"] == "1%", (key, data["exit_load"])


def test_exit_load_is_na_when_the_page_shows_none():
    # Same saved Dynamic Debt page with the exit load row relabelled so no exit load is shown.
    def no_exit_load(html, main):
        return html.replace("Exit Load", "Exit Fee"), main.replace("Exit Load", "Exit Fee")
    for data in both("debt", no_exit_load):
        assert data["exit_load"] == "N/A", data["exit_load"]


# 2. Gold minimum investment -------------------------------------------------------------------

def test_gold_minimum_investment_is_parsed_from_the_about_text():
    for data in both("gold"):
        assert data["min_investment_lumpsum"] == "100" and data["min_investment_sip"] == "100", data


def test_gold_minimum_investment_is_na_when_the_about_text_is_missing():
    def no_about(html, main):
        return (html.replace("Minimum investment for lump sum payment", "Minimum"),
                main.replace("Minimum investment for lump sum payment", "Minimum"))
    for data in both("gold", no_about):
        assert data["min_investment_lumpsum"] == "N/A" and data["min_investment_sip"] == "N/A", data


def test_other_funds_minimum_investment_still_comes_from_the_overview_card():
    for key in ("infra", "debt", "hybrid"):
        for data in both(key):
            assert data["min_investment_lumpsum"] == "100" and data["min_investment_sip"] == "100", (key, data)


# 3. risk level --------------------------------------------------------------------------------

EXPECTED_RISK = {  # the label each saved page shows in its Overview card
    "infra": "Very High Risk", "mid": "Very High Risk", "small": "Very High Risk", "flexi": "Very High Risk",
    "value": "Very High Risk", "debt": "Moderately High risk", "lowdur": "Moderate Risk",
    "gold": "High Risk", "hybrid": "Very High Risk", "eqsav": "Moderately High risk",
}


def test_risk_level_is_the_full_label_the_page_shows():
    for key, label in EXPECTED_RISK.items():
        for data in both(key):
            assert data["risk_level"] == label, (key, data["risk_level"], label)


# 4. daily % change ----------------------------------------------------------------------------

def test_daily_change_is_none_not_zero_when_the_page_does_not_show_it():
    for key in ("small", "debt", "lowdur"):
        for data in both(key):
            assert data["daily_pct_change"] is None, (key, data["daily_pct_change"])


def test_daily_change_is_still_captured_when_the_page_shows_it():
    # Rendered text only: the browser path is the one used in production. BeautifulSoup text splits the
    # figure into "-0.2 % 1D" and is not used when a browser page is available.
    for key, expected in (("infra", -0.2), ("gold", 0.3)):
        assert extract(key, live=True)["daily_pct_change"] == expected, key


# 5. N/A flows through validation and documents ---------------------------------------------------

def _record(key: str, live: bool = True):
    record, err = validate_fund_record(extract(key, live))
    assert record is not None, err
    return record


def test_records_with_na_values_pass_validation():
    for key in ("small", "debt", "lowdur", "gold"):
        record = _record(key)
        assert record.daily_pct_change is None or record.daily_pct_change != 0


def test_documents_say_na_for_missing_values_and_never_zero_or_blank():
    text = record_to_text(_record("small"))
    assert "Daily % Change: N/A" in text
    assert "0.0" not in text.replace("0.0%", "")  # no placeholder number
    for key in IDS:
        for line in record_to_text(_record(key)).splitlines():
            label, _, value = line.partition(": ")
            assert value.strip(), f"blank value in {key}: {line!r}"
    gold = record_to_text(_record("gold"))
    assert "Min Investment (Lumpsum): 100" in gold and "Exit Load: 1%" in gold
    debt = record_to_text(_record("debt"))
    assert "Exit Load: 0%" in debt and "Risk Level: Moderately High risk" in debt and "Daily % Change: N/A" in debt


# 6. known benchmark typo (INDmoney spells "Infrastructure" wrong on the Infrastructure Fund page) ------------

EXPECTED_BENCHMARK = {  # unchanged by the spelling fix
    "mid": "Nifty Midcap 150 TR INR", "small": "BSE 250 SmallCap TR INR", "flexi": "Nifty 500 TR INR",
    "value": "Nifty 500 TR INR", "debt": "Nifty Composite Debt TR INR", "lowdur": "NIFTY Low Duration Debt Index TR INR",
    "gold": "Domestic Price of Gold", "hybrid": "Nifty 50 TR INR", "eqsav": "NIFTY Equity Savings TR INR",
}


def test_infrastructure_page_gives_the_corrected_benchmark():
    assert "Infrasturcture" in _fixture("infra", "page.html")  # the saved page really has the typo
    for data in both("infra"):
        assert data["benchmark"] == "BSE India Infrastructure TRI TR INR", data["benchmark"]


def test_every_other_funds_benchmark_is_unchanged():
    for key, expected in EXPECTED_BENCHMARK.items():
        for data in both(key):
            assert data["benchmark"] == expected, (key, data["benchmark"])


def test_a_page_that_already_has_the_correct_spelling_passes_through():
    def correct(html, main):
        return html.replace("Infrasturcture", "Infrastructure"), main.replace("Infrasturcture", "Infrastructure")
    for data in both("infra", correct):
        assert data["benchmark"] == "BSE India Infrastructure TRI TR INR"


def test_the_override_is_an_exact_match_after_whitespace_normalisation_only():
    fix = scraper._fix_known_benchmark_typo
    assert fix("BSE India Infrasturcture TRI TR INR") == "BSE India Infrastructure TRI TR INR"
    assert fix("  BSE India   Infrasturcture TRI TR INR ") == "BSE India Infrastructure TRI TR INR"
    for untouched in ("BSE India Infrasturcture TRI", "Nifty 50 TR INR", "BSE India Infrastructure TRI TR INR", "Infrasturcture", "", None):
        assert fix(untouched) == untouched, untouched


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
