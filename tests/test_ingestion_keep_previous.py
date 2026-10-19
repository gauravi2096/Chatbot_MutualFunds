"""
Offline tests (no network, no Chroma, no real data files) for the data-pipeline guards:
the validation quality gate, keeping a fund's previous record when its scrape is rejected,
the ingestion status file, the benchmark rules, and N/A handling for a missing NAV.
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_0.schema import FundRecord
from phase_0.source_registry import RegisteredSource
from phase_1.documents import record_to_text
from phase_1.run_ingestion import (
    STATUS_DROPPED,
    STATUS_KEPT_PREVIOUS,
    STATUS_OK,
    STATUS_RETRIED,
    resolve_fund,
    write_status,
)
from phase_1.scraper import _benchmark_from_embedded_data, _is_acceptable_benchmark, extract_fund_data
from phase_1.validation import DATA_FIELDS, MIN_POPULATED_FIELDS, validate_fund_record

FUND_ID = "hdfc-infrastructure-fund-direct-plan-growth-option-3315"
URL = f"https://www.indmoney.com/mutual-funds/{FUND_ID}"
SRC = RegisteredSource(fund_id=FUND_ID, fund_name="HDFC Infrastructure Fund", url=URL)

# What the scraper returns when the page has no data: N/A (None for numbers) everywhere.
EMPTY_RAW = {
    "fund_id": FUND_ID, "fund_name": "HDFC Infrastructure Fund", "source_url": URL,
    "scraped_at": "2026-10-18T09:01:11Z", "nav": None, "daily_pct_change": None, "aum": "N/A",
    "expense_ratio": "N/A", "min_investment_lumpsum": "N/A", "min_investment_sip": "N/A",
    "exit_load": "N/A", "elss_lock_in": "N/A", "cagr_1y": "N/A", "cagr_3y": "N/A", "cagr_5y": "N/A",
    "since_inception": "N/A", "equity_pct": "N/A", "debt_cash_pct": "N/A", "market_cap_split": "N/A",
    "top_holdings": "N/A", "risk_level": "N/A", "benchmark": "BSE India Infrastructure TRI TR INR",
}
GOOD_RAW = {
    **EMPTY_RAW, "scraped_at": "2026-10-14T09:40:25Z", "nav": 49.88, "nav_date": "2026-10-13",
    "daily_pct_change": -0.3, "aum": "2251 Cr", "expense_ratio": "1.35%", "min_investment_lumpsum": "100",
    "min_investment_sip": "100", "exit_load": "1%", "elss_lock_in": "No Lock-in", "cagr_1y": "-7.1%",
    "cagr_3y": "11.55%", "cagr_5y": "16.74%", "since_inception": "11.44%", "equity_pct": "98.8%",
    "debt_cash_pct": "1.2%", "market_cap_split": "Large cap 49.3%", "top_holdings": "Larsen & Toubro Ltd(7.03%)",
    "risk_level": "Very High Risk",
}


def _no_sleep(_seconds):
    pass


def test_there_are_19_data_fields():
    assert len(DATA_FIELDS) == 19, DATA_FIELDS
    assert "nav" in DATA_FIELDS and "benchmark" in DATA_FIELDS
    assert "fund_id" not in DATA_FIELDS and "scraped_at" not in DATA_FIELDS


def test_empty_record_is_rejected_and_good_record_accepted():
    record, err = validate_fund_record(EMPTY_RAW)
    assert record is None and "NAV" in err, err
    record, err = validate_fund_record(GOOD_RAW)
    assert record is not None and err is None


def test_zero_nav_is_rejected():
    record, err = validate_fund_record({**GOOD_RAW, "nav": 0.0})
    assert record is None and "NAV" in err


def test_field_count_threshold_is_10_of_19():
    na = {k: "N/A" for k in DATA_FIELDS if k not in ("nav", "nav_date", "daily_pct_change")}
    keep = ["aum", "expense_ratio", "exit_load", "cagr_1y", "cagr_3y", "cagr_5y", "since_inception", "risk_level"]
    base = {**EMPTY_RAW, **na, "nav": 49.0}  # populated so far: nav only
    # nav + 8 kept fields = 9 populated -> rejected
    nine = {**base, **{k: GOOD_RAW[k] for k in keep}}
    record, err = validate_fund_record(nine)
    assert record is None and "9/19" in err, err
    # one more field = 10 populated -> accepted
    ten = {**nine, "benchmark": "Nifty 500 TR INR"}
    record, err = validate_fund_record(ten)
    assert record is not None, err
    assert MIN_POPULATED_FIELDS == 10


def test_rejected_scrape_keeps_previous_record_and_reports_kept_previous():
    previous_record, _ = validate_fund_record(GOOD_RAW)
    calls, sleeps = [], []

    def scrape_empty(_src):
        calls.append(1)
        return dict(EMPTY_RAW)

    record, entry = resolve_fund(SRC, scrape_empty, {FUND_ID: previous_record}, retries=2, backoff=3, sleep=sleeps.append)
    assert len(calls) == 3, "1 attempt + 2 retries"
    assert sleeps == [3, 6], sleeps
    assert record is previous_record
    assert record.scraped_at == "2026-10-14T09:40:25Z" and record.nav == 49.88  # unchanged, old timestamp kept
    assert entry["status"] == STATUS_KEPT_PREVIOUS == "kept_previous"
    assert entry["attempts"] == 3 and entry["previous_scraped_at"] == "2026-10-14T09:40:25Z"
    assert "NAV" in entry["reason"]


def test_no_previous_record_drops_the_fund():
    record, entry = resolve_fund(SRC, lambda _s: dict(EMPTY_RAW), {}, retries=2, backoff=0, sleep=_no_sleep)
    assert record is None and entry["status"] == STATUS_DROPPED


def test_previous_record_that_is_itself_empty_is_not_kept():
    bad_previous = FundRecord.model_validate(EMPTY_RAW)
    record, entry = resolve_fund(SRC, lambda _s: dict(EMPTY_RAW), {FUND_ID: bad_previous}, retries=1, backoff=0, sleep=_no_sleep)
    assert record is None and entry["status"] == STATUS_DROPPED


def test_fetch_failure_and_exceptions_are_retried_then_kept():
    previous_record, _ = validate_fund_record(GOOD_RAW)
    outcomes = iter([None, RuntimeError("browser crashed"), None])
    def flaky(_src):
        out = next(outcomes)
        if isinstance(out, Exception):
            raise out
        return out
    record, entry = resolve_fund(SRC, flaky, {FUND_ID: previous_record}, retries=2, backoff=0, sleep=_no_sleep)
    assert record is previous_record and entry["status"] == STATUS_KEPT_PREVIOUS


def test_success_on_first_try_is_ok_and_after_a_retry_is_retried():
    record, entry = resolve_fund(SRC, lambda _s: dict(GOOD_RAW), {}, retries=2, backoff=0, sleep=_no_sleep)
    assert entry["status"] == STATUS_OK and entry["attempts"] == 1 and entry["populated"] >= 10
    outcomes = iter([dict(EMPTY_RAW), dict(GOOD_RAW)])
    record, entry = resolve_fund(SRC, lambda _s: next(outcomes), {}, retries=2, backoff=0, sleep=_no_sleep)
    assert entry["status"] == STATUS_RETRIED and entry["attempts"] == 2 and record.nav == 49.88


def test_status_file_lists_every_fund():
    previous_record, _ = validate_fund_record(GOOD_RAW)
    _, kept = resolve_fund(SRC, lambda _s: dict(EMPTY_RAW), {FUND_ID: previous_record}, retries=0, backoff=0, sleep=_no_sleep)
    _, ok = resolve_fund(SRC, lambda _s: dict(GOOD_RAW), {}, retries=0, backoff=0, sleep=_no_sleep)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ingestion_status.json"
        write_status(path, [kept, ok])
        data = json.loads(path.read_text())
    assert data["summary"] == {"kept_previous": 1, "ok": 1}
    assert [f["status"] for f in data["funds"]] == ["kept_previous", "ok"]


def test_bare_sp_bse_is_never_an_acceptable_benchmark():
    for bad in ("S&P BSE", "s&p  bse", "BSE", "Nifty", "N/A", "", None):
        assert not _is_acceptable_benchmark(bad), bad
    for good in ("BSE 250 SmallCap TR INR", "S&P BSE 500 TRI", "Nifty 500 TR INR", "Domestic Price of Gold"):
        assert _is_acceptable_benchmark(good), good


def test_benchmark_is_read_from_embedded_overview_data():
    html = '<script>{"info":[{"name":"Expense ratio","value":"0.75%"},{"name":"Benchmark","value":"BSE 250 SmallCap TR INR","description":"x"}]}</script>'
    assert _benchmark_from_embedded_data(html) == "BSE 250 SmallCap TR INR"
    assert _benchmark_from_embedded_data('{"name":"Benchmark","value":"S\\u0026P BSE 500 TRI"}') == "S&P BSE 500 TRI"
    assert _benchmark_from_embedded_data("<html></html>") is None


def test_hidden_sp_bse_link_never_becomes_the_benchmark():
    html = (
        "<html><body><main>" + "HDFC Fund text " * 60 + "</main>"
        '<footer><ul><li><a href="/indices/sandp-bse-largecap">S&amp;P BSE LargeCap</a></li></ul></footer></body></html>'
    )
    data = extract_fund_data(html, "some-other-fund", "Some Fund", "https://www.indmoney.com/mutual-funds/some-other-fund")
    assert data["benchmark"] == "N/A", data["benchmark"]
    # the one fund with a hard-coded fallback still gets it
    data = extract_fund_data(html, FUND_ID, "HDFC Infrastructure Fund", URL)
    assert data["benchmark"] == "BSE India Infrastructure TRI TR INR"


def test_missing_nav_is_none_not_zero_and_prints_as_na():
    data = extract_fund_data("<html><body><main>" + "no prices here " * 60 + "</main></body></html>", FUND_ID, "HDFC Infrastructure Fund", URL)
    assert data["nav"] is None
    record = FundRecord.model_validate(data)
    assert record.nav is None
    assert "NAV: N/A" in record_to_text(record)
    zero = FundRecord.model_validate({**GOOD_RAW, "nav": 0.0})
    assert "NAV: N/A" in record_to_text(zero)
    good = FundRecord.model_validate(GOOD_RAW)
    assert "NAV: 49.88" in record_to_text(good)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
