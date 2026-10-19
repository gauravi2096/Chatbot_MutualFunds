"""
Offline tests (saved pages in tests/fixtures, no network): validated top-holdings parsing and the
daily-change rules (None -> N/A, a genuine 0.0 is a value).
"""

import json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_scraper_field_fixes as fx
from phase_1.documents import record_to_text
from phase_1.scraper import _extract_top_holdings, extract_fund_data
from phase_1.validation import MIN_POPULATED_FIELDS, count_populated, validate_fund_record

BEFORE = json.loads((fx.FIXTURES / "top_holdings_before.json").read_text())  # output before this change
DYNAMIC_TERM = ("7.34% Govt Stock 2064(14.7%), Rec Limited(5.34%), "
                "National Bank For Agriculture And Rural Development(5.19%)")
ULTRA_SHORT = ("Small Industries Development Bank Of India(5.55%), 6.17% Govt Stock 2028(4.72%), "
               "Jubilant Beverages Limited(4.05%)")


# top holdings on the real saved pages ---------------------------------------------------------------

def test_dynamic_term_has_exactly_three_holdings_with_names_and_percentages():
    for data in fx.both("debt"):
        assert data["top_holdings"] == DYNAMIC_TERM, data["top_holdings"]


def test_ultra_short_has_exactly_three_holdings_with_names_and_percentages():
    for data in fx.both("lowdur"):
        assert data["top_holdings"] == ULTRA_SHORT, data["top_holdings"]


def test_the_other_eight_funds_are_identical_to_the_output_before_the_change():
    for key in fx.IDS:
        if key in ("debt", "lowdur"):
            continue
        for live, mode in ((True, "live"), (False, "html")):
            assert fx.extract(key, live)["top_holdings"] == BEFORE[key][mode], (key, mode)


def test_a_fund_holding_a_single_etf_keeps_its_one_holding():
    # The Gold page says "top 3 holdings" but lists the one ETF it holds (100.12%).
    for data in fx.both("gold"):
        assert data["top_holdings"] == "HDFC Gold ETF(100.12%)"


# invented strings ------------------------------------------------------------------------------------

def test_names_may_contain_percent_period_hyphen_apostrophe_ampersand_comma_and_digits():
    text = ("Q. What are the top holdings? The top 4 holdings of the fund are 7.34% Govt Stock 2064(14.7%), "
            "Coca-Cola Hbc Ag(5.1%), Moody's Corp & Co.(4.25%), Tata Motors, Ltd 2.0(3%) Who is the manager?")
    assert _extract_top_holdings(text) == (
        "7.34% Govt Stock 2064(14.7%), Coca-Cola Hbc Ag(5.1%), Moody's Corp & Co.(4.25%), Tata Motors, Ltd 2.0(3%)"
    )


def test_item_count_must_equal_n_when_n_is_given():
    assert _extract_top_holdings("The top 3 holdings of the fund are A Ltd(5%), B Ltd(4%), C Ltd(3%)?") == "A Ltd(5%), B Ltd(4%), C Ltd(3%)"
    # more items than N is rejected, not trimmed
    assert _extract_top_holdings("The top 2 holdings of the fund are A Ltd(5%), B Ltd(4%), C Ltd(3%)?") is None
    # fewer than N while more bracketed items clearly follow is a broken parse, not a short list
    assert _extract_top_holdings("The top 3 holdings of the fund are A Ltd(5%), B Ltd(4%), C (Class A) Ltd(3%)?") is None


def test_without_n_at_least_one_item_is_required():
    assert _extract_top_holdings("The holdings of the fund are A Ltd(5%), B Ltd(4%)?") == "A Ltd(5%), B Ltd(4%)"
    assert _extract_top_holdings("The holdings of the fund are nothing listed?") is None


def test_prose_only_text_gives_none_and_na_never_prose():
    prose = ("HDFC Fund has allocated its funds majorly in Government, Financial Services, Industrial. "
             "Its top holdings are Rec Limited, National Bank, Small Industries Development Bank. " * 3)
    assert _extract_top_holdings(prose) is None
    html = "<html><body><main>" + prose + " Holdings " + prose + "</main></body></html>"
    data = extract_fund_data(html, "x", "Some Fund", "https://www.indmoney.com/mutual-funds/x")
    assert data["top_holdings"] == "N/A", data["top_holdings"]


def test_a_fallback_result_is_accepted_only_if_it_is_a_clean_list():
    # No "top N ... are" sentence; the "Holdings" section fallback holds a clean list -> accepted.
    assert _extract_top_holdings("Holdings A Ltd(5%), B Ltd(4%) See all") == "A Ltd(5%), B Ltd(4%)"
    # ... but the same section with a sentence of prose in it is rejected.
    assert _extract_top_holdings("Holdings The fund invests broadly in banks and A Ltd(5%) See all") is None


# daily change -----------------------------------------------------------------------------------------

def _good_record():
    record, err = validate_fund_record(fx.extract("mid", True))
    assert record is not None, err
    return record


def _daily_line(record):
    return [ln for ln in record_to_text(record).splitlines() if ln.startswith("Daily % Change")][0]


def test_daily_change_prints_na_only_when_none():
    record = _good_record()
    assert _daily_line(record.model_copy(update={"daily_pct_change": None})) == "Daily % Change: N/A"
    assert _daily_line(record.model_copy(update={"daily_pct_change": 0.0})) == "Daily % Change: 0.00%"
    assert _daily_line(record.model_copy(update={"daily_pct_change": -0.2})) == "Daily % Change: -0.20%"
    assert _daily_line(record.model_copy(update={"daily_pct_change": 1.5})) == "Daily % Change: 1.50%"


def test_zero_nav_still_prints_na():
    record = _good_record()
    assert "NAV: N/A" in record_to_text(record.model_copy(update={"nav": 0.0}))
    assert "NAV: N/A" in record_to_text(record.model_copy(update={"nav": None}))


def test_validation_does_not_reject_a_genuine_zero_daily_change():
    record = _good_record()
    assert count_populated(record.model_copy(update={"daily_pct_change": 0.0})) == count_populated(
        record.model_copy(update={"daily_pct_change": 0.5}))
    # A record with exactly the minimum populated fields, one of them a 0.0 daily change, is accepted.
    from phase_1.validation import DATA_FIELDS
    raw = {"fund_id": "x", "fund_name": "X", "source_url": "https://www.indmoney.com/mutual-funds/x",
           **{k: "N/A" for k in DATA_FIELDS if k not in ("nav", "nav_date", "daily_pct_change")},
           "nav": 10.0, "daily_pct_change": 0.0}
    names = ["aum", "expense_ratio", "exit_load", "cagr_1y", "cagr_3y", "cagr_5y", "since_inception", "risk_level"]
    for n in names:
        raw[n] = "1%"
    assert count_populated(__import__("phase_0.schema", fromlist=["FundRecord"]).FundRecord.model_validate(raw)) == MIN_POPULATED_FIELDS
    record, err = validate_fund_record(raw)
    assert record is not None, err
    raw["daily_pct_change"] = None  # nine now
    record, err = validate_fund_record(raw)
    assert record is None and "9/19" in err


def test_scraper_stores_a_real_zero_daily_change_as_zero():
    html = ("<html><body><main>" + "filler text " * 60 + " ₹100.50 ▼0.00% 1D NAV as on 16 Oct 2026 "
            + "filler text " * 20 + "</main></body></html>")
    data = extract_fund_data(html, "x", "Some Fund", "https://www.indmoney.com/mutual-funds/x")
    assert data["daily_pct_change"] == 0.0 and data["daily_pct_change"] is not None


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
