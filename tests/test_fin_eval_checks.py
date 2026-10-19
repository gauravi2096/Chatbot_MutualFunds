"""
Offline tests (temp files only, no network, no real data) for fin_eval's preflight check and its numeric
answer matching. The preflight tests also run fin_eval.py itself with --preflight-only to check exit codes.
"""

import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fin_eval_checks import (NUMERIC_FIELDS, daily_na_ok, facts_ok, holdings_ok, numbers_in, numeric_match,
                             parse_holdings, parse_number, preflight, run_preflight)

FUNDS = {"fund-a": "HDFC Alpha Fund", "fund-b": "HDFC Beta Fund"}


def make_repo(tmp: Path, age_hours=1.0, funds_names=None, registry_names=None, chroma_names=None, chroma=True) -> Path:
    """A minimal fake repo: funds.json, the registry JSON and a Chroma-style sqlite file."""
    funds_names = funds_names or FUNDS
    registry_names = registry_names or FUNDS
    chroma_names = chroma_names or FUNDS
    stamp = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp / "phase_1/data/chroma").mkdir(parents=True)
    (tmp / "phase_0/data").mkdir(parents=True)
    (tmp / "phase_1/data/funds.json").write_text(json.dumps(
        {"last_updated": "x", "funds": [{"fund_id": i, "fund_name": n, "scraped_at": stamp} for i, n in funds_names.items()]}))
    (tmp / "phase_0/data/source_registry.json").write_text(json.dumps(
        {"sources": [{"fund_id": i, "fund_name": n, "url": f"https://x/{i}"} for i, n in registry_names.items()]}))
    if chroma:
        con = sqlite3.connect(tmp / "phase_1/data/chroma/chroma.sqlite3")
        con.execute("CREATE TABLE embedding_metadata (id INTEGER, key TEXT, string_value TEXT, int_value INTEGER)")
        for n, (fund_id, name) in enumerate(chroma_names.items(), 1):
            con.executemany("INSERT INTO embedding_metadata VALUES (?, ?, ?, NULL)",
                            [(n, "fund_id", fund_id), (n, "fund_name", name), (n, "source_url", f"https://x/{fund_id}")])
        con.commit()
        con.close()
    return tmp


def run_cli(repo: Path, *flags: str):
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "fin_eval.py"), "--repo", str(repo), "--preflight-only", *flags],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def with_repo(**kwargs):
    tmp = tempfile.TemporaryDirectory()
    return tmp, make_repo(Path(tmp.name), **kwargs)


# --- preflight ---------------------------------------------------------------------------------------

def test_fresh_and_matching_data_passes_and_prints_the_summary():
    tmp, repo = with_repo()
    with tmp:
        lines = []
        assert preflight(repo, offline=False, allow_stale=False, out=lines.append) is True
        text = "\n".join(lines)
        assert "2 funds" in text and "h old" in text and "all match" in text and "all checks passed" in text
        assert "git:" in text
        code, out = run_cli(repo)
        assert code == 0 and "all checks passed" in out, out


def test_stale_data_stops_an_online_run():
    tmp, repo = with_repo(age_hours=60)
    with tmp:
        code, out = run_cli(repo)
        assert code == 2 and "STOP" in out and "60." in out and "limit 48 h" in out, out
        _, problems = run_preflight(repo)
        assert len(problems) == 1


def test_just_under_the_limit_passes():
    tmp, repo = with_repo(age_hours=47)
    with tmp:
        assert run_cli(repo)[0] == 0


def test_an_old_fund_name_in_funds_json_stops_an_online_run():
    tmp, repo = with_repo(funds_names={"fund-a": "HDFC Alpha Old Name", "fund-b": "HDFC Beta Fund"},
                          chroma_names={"fund-a": "HDFC Alpha Old Name", "fund-b": "HDFC Beta Fund"})
    with tmp:
        code, out = run_cli(repo)
        assert code == 2 and "differs from the registry" in out and "HDFC Alpha Old Name" in out, out


def test_a_chroma_name_that_differs_from_funds_json_stops_an_online_run():
    tmp, repo = with_repo(chroma_names={"fund-a": "HDFC Alpha Fund", "fund-b": "HDFC Beta Old Name"})
    with tmp:
        code, out = run_cli(repo)
        assert code == 2 and "Chroma index differs from funds.json" in out and "Beta Old Name" in out, out


def test_a_missing_chroma_index_stops_an_online_run():
    tmp, repo = with_repo(chroma=False)
    with tmp:
        code, out = run_cli(repo)
        assert code == 2 and "Chroma index not found" in out, out


def test_allow_stale_bypasses_every_problem():
    tmp, repo = with_repo(age_hours=100, funds_names={"fund-a": "Old", "fund-b": "HDFC Beta Fund"},
                          chroma_names={"fund-a": "Older", "fund-b": "HDFC Beta Fund"})
    with tmp:
        assert run_cli(repo)[0] == 2
        code, out = run_cli(repo, "--allow-stale")
        assert code == 0 and "bypassed by --allow-stale" in out and "STOP" not in out, out


def test_offline_prints_warnings_and_never_stops():
    tmp, repo = with_repo(age_hours=100, funds_names={"fund-a": "Old", "fund-b": "HDFC Beta Fund"},
                          chroma_names={"fund-a": "Older", "fund-b": "HDFC Beta Fund"})
    with tmp:
        code, out = run_cli(repo, "--offline")
        assert code == 0 and "WARNING" in out and "STOP" not in out and "continuing" in out, out
    tmp, repo = with_repo(chroma=False)
    with tmp:
        code, out = run_cli(repo, "--offline")
        assert code == 0 and "WARNING: Chroma index not found" in out, out


def test_the_preflight_does_not_modify_the_chroma_file():
    tmp, repo = with_repo()
    with tmp:
        path = repo / "phase_1/data/chroma/chroma.sqlite3"
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        run_preflight(repo)
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before


# --- numeric matching --------------------------------------------------------------------------------

def test_daily_change_formats_all_count_as_equal():
    for answer in ("-0.2", "-0.20", "-0.20%", "-0.20 %", "−0.20%", "− 0.2", "–0.2%",
                   "**\u20110.2\u202f%**", "\u20100.20%",  # non-breaking hyphen + narrow no-break space, as LLM answers write them
                   "The daily change of HDFC Mid Cap Fund is −0.20% today.", "NAV fell by -0.2 % on 1D"):
        assert numeric_match(answer, -0.2), answer
        assert numeric_match(answer, "-0.2%"), answer
        assert numeric_match(answer, "-0.20"), answer


def test_a_different_figure_or_sign_does_not_match():
    assert not numeric_match("0.2%", -0.2)       # sign matters
    assert not numeric_match("-0.3%", -0.2)
    assert not numeric_match("-0.21%", -0.2)     # outside the 0.005 tolerance
    assert numeric_match("-0.204%", -0.2) and not numeric_match("-0.206%", -0.2)
    assert not numeric_match("no figure here", -0.2)


def test_zero_daily_change_matches_zero_in_any_format():
    for answer in ("0", "0.0", "0.00", "0.00%", "0.00 %", "unchanged at 0.00%"):
        assert numeric_match(answer, 0.0), answer
    assert not numeric_match("0.2%", 0.0)


def test_ranges_and_dates_do_not_create_negative_numbers():
    assert numbers_in("3-5 years") == [3.0, 5.0]
    assert numbers_in("on 16 Oct 2026 the NAV was 221.06") == [16.0, 2026.0, 221.06]
    assert numbers_in("returns of -7.1% and −2.5%") == [-7.1, -2.5]


def test_other_numeric_fields_use_the_same_comparison():
    # trailing zeros and units are where plain text matching failed: "-7.1%" vs "-7.10%", "1%" vs "1.0%"
    assert numeric_match("1-year return is -7.10%", "-7.1%")
    assert numeric_match("The exit load is 1.0%", "1%")
    assert numeric_match("expense ratio is 1.350%", "1.35%")
    assert numeric_match("AUM is ₹2,251 Cr", "2251 Cr")
    assert numeric_match("NAV is 49.640", 49.64)
    assert {"daily_pct_change", "cagr_1y", "exit_load", "nav", "aum"} <= NUMERIC_FIELDS
    assert parse_number("N/A") is None and parse_number("No Lock-in") is None


# --- regression-case scorers (#71-#77) and the shared scorer ---------------------------------------------

HOLDINGS = "7.34% Govt Stock 2064(14.7%), Rec Limited(5.34%), National Bank For Agriculture And Rural Development(5.19%)"


def test_parse_holdings_reads_clean_lists_and_rejects_prose():
    assert parse_holdings(HOLDINGS) == [("7.34% Govt Stock 2064", 14.7), ("Rec Limited", 5.34),
                                        ("National Bank For Agriculture And Rural Development", 5.19)]
    assert parse_holdings("HDFC Gold ETF(100.12%)") == [("HDFC Gold ETF", 100.12)]
    assert parse_holdings("HDFC Dynamic Term Fund has allocated its funds majorly in Government. Its top holdings are Rec") is None
    assert parse_holdings("Small Industries Development Bank Of India(5.55%), and more text") is None
    assert parse_holdings("N/A") is None and parse_holdings(None) is None and parse_holdings("") is None


def test_holdings_answer_needs_every_name_and_percentage_numerically():
    items = parse_holdings(HOLDINGS)
    good = ("The top holdings are 7.34% Govt Stock 2064 (14.70%), Rec Limited (5.34 %) and "
            "National Bank For Agriculture And Rural Development (5.19%).")
    assert holdings_ok(good, items)
    assert not holdings_ok(good.replace("Rec Limited (5.34 %) and ", ""), items)           # a holding missing
    assert not holdings_ok(good.replace("5.34", "5.43"), items)                           # a wrong percentage
    assert not holdings_ok("The fund holds government securities and corporate bonds.", items)


def test_daily_na_answer_must_say_unavailable_and_give_no_figure():
    assert daily_na_ok("The daily change is not available in the data.")
    assert daily_na_ok("I don't have the daily change for HDFC Small Cap Fund (NAV 155.06 on 16 Oct 2026).")
    assert not daily_na_ok("The daily change is 0.0%.")
    assert not daily_na_ok("The daily change is 0.00, but other data is not available.")
    assert not daily_na_ok("The daily change is -0.2%, data not available for other periods.")
    assert not daily_na_ok("The NAV is 155.06.")                                          # says nothing about it being missing


def test_shared_scorer_handles_numbers_gaps_and_text_fields():
    rec = {"nav": 49.64, "daily_pct_change": -0.2, "cagr_1y": "-7.1%", "exit_load": "1%", "risk_level": "Very High Risk",
           "benchmark": "BSE India Infrastructure TRI TR INR", "aum": "N/A"}
    assert facts_ok("NAV is 49.64", [(rec, "nav")]) == (True, False)
    assert facts_ok("The daily change is \u22120.20%", [(rec, "daily_pct_change")]) == (True, False)
    assert facts_ok("1 year return: \u20117.10 %", [(rec, "cagr_1y")]) == (True, False)
    assert facts_ok("exit load 1.0%", [(rec, "exit_load")]) == (True, False)
    assert facts_ok("risk level is Very High Risk", [(rec, "risk_level")])[0]
    assert facts_ok("BSE India Infrastructure", [(rec, "benchmark")])[0]
    assert facts_ok("AUM is not available", [(rec, "aum")]) == (True, True)               # N/A in the data: honest answer wins
    assert facts_ok("AUM is 5000 Cr", [(rec, "aum")]) == (False, True)
    assert facts_ok("NAV is 49.65", [(rec, "nav")])[0] is False
    zero = dict(rec, daily_pct_change=0.0)
    assert facts_ok("0.00%", [(zero, "daily_pct_change")]) == (True, False)               # a genuine zero is a value


def test_fin_eval_offline_report_splits_original_new_and_combined():
    with tempfile.TemporaryDirectory() as out:
        r = subprocess.run([sys.executable, str(PROJECT_ROOT / "fin_eval.py"), "--offline", "--out", out],
                           capture_output=True, text=True, timeout=300, cwd=str(PROJECT_ROOT))
        assert r.returncode == 0, r.stderr[-500:]
        report = (Path(out) / "fin_eval_report.md").read_text()
        results = json.loads((Path(out) / "fin_eval_results.json").read_text())
    assert len(results) == 77 and [x["id"] for x in results] == list(range(1, 78))
    assert all(x["kind"] == "regression" for x in results[70:]) and not any(x["kind"] == "regression" for x in results[:70])
    assert "Original 70 questions: **70/70 = 100%**" in report
    assert "Fixed-field regression, 7 new questions (#71-#77)" in report and "Combined:" in report


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
