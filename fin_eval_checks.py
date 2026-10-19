"""
Helpers for fin_eval.py (kept in a module so they can be tested offline):
  * preflight(): print the state of the code and data before a run, and stop an online run on stale or
    mismatched data.
  * numeric answer matching: compare the figure in an answer with a numeric ground truth as a number.
Standard library only; it never opens the Chroma store for writing.
"""

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

MAX_AGE_HOURS = 48

# ---------------------------------------------------------------------------------------------
# numeric matching
# ---------------------------------------------------------------------------------------------

# Fields whose ground truth is a number: compared numerically, not as text ("-0.2" == "-0.20 %").
NUMERIC_FIELDS = {
    "nav", "daily_pct_change", "aum", "expense_ratio", "exit_load", "min_investment_lumpsum",
    "min_investment_sip", "cagr_1y", "cagr_3y", "cagr_5y", "since_inception", "equity_pct", "debt_cash_pct",
}
# A number with an optional sign. A hyphen-minus, other hyphen (U+2010 to U+2012, U+FE63, U+FF0D) or minus sign (U+2212) counts
# as a sign when it is right before the digits, with at most one space. An en dash (U+2013) is also used as a separator
# ("Rec Limited – 5.34%"), so it counts as a minus only when a digit follows it immediately ("–0.2%"). A dash glued to
# the previous word ("3-5 years") is a range, not a minus.
_MINUS = "-\u2010\u2011\u2012\u2212\ufe63\uff0d"
_NUMBER = re.compile(r"(?<![\w.])((?:[" + _MINUS + r"]\s?)|(?:\u2013(?=\d)))?(\d[\d,]*(?:\.\d+)?)")


def numbers_in(text: str) -> List[float]:
    """Every number in `text`, signed: '-0.20 %' -> -0.2, 'Rs 2,251 Cr' -> 2251.0."""
    out = []
    for m in _NUMBER.finditer(str(text)):
        try:
            value = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        out.append(-value if m.group(1) else value)
    return out


def parse_number(value) -> Optional[float]:
    """The single number in a ground-truth value such as '-7.1%' or '2251 Cr', else None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    found = numbers_in(value)
    return found[0] if len(found) == 1 else None


def numeric_match(answer: str, truth, tolerance: float = 0.005) -> bool:
    """True if the answer contains a figure equal to `truth` within `tolerance`."""
    target = parse_number(truth)
    if target is None:
        raise ValueError(f"ground truth is not a single number: {truth!r}")
    return any(abs(n - target) <= tolerance for n in numbers_in(answer))


# ---------------------------------------------------------------------------------------------
# scoring (shared by fin_eval.py and the baseline re-score)
# ---------------------------------------------------------------------------------------------

GAP_PHRASES = ["don't have", "do not have", "not available", "does not contain", "doesn't contain",
               "not provided", "no data", "unavailable", "not listed", "not found", "n/a",
               "couldn't find", "could not find", "not in the", "missing"]


def norm(s):
    s = s.lower().replace("\u2212", "-").replace("\u2013", "-")
    return re.sub(r"[\s,\u20b9]|rs\.?|inr", "", s)


def is_na(v, field=None):
    if field == "daily_pct_change":
        return v in ("N/A", None, "")  # a daily change of exactly 0.0 is a real value
    return v in ("N/A", None, "", 0, 0.0)


def fact_for(record: dict, field: str) -> Optional[str]:
    """Normalized substring the answer must contain for this field, or None if the data is N/A."""
    v = record[field]
    if is_na(v, field):
        return None
    v = str(v)
    if field == "risk_level":
        return norm(v).replace("risk", "")
    if field == "benchmark":
        return norm(v.split(" TR")[0])
    if field == "top_holdings":
        first = v.split("(")[0]
        return norm(re.sub(r"\b(the|ltd|limited)\b", "", first.lower()))
    if field == "elss_lock_in":
        return "nolock"
    return norm(v)


def facts_ok(msg: str, pairs) -> Tuple[bool, bool]:
    """
    pairs: list of (record dict, field). Returns (ok, gap); gap=True when every expected value is N/A
    (then an honest "not available" is the right answer). Numeric fields compare as numbers.
    """
    m = norm(msg)
    checks, gaps = [], 0
    for record, field in pairs:
        expected = fact_for(record, field)
        if expected is None:
            gaps += 1
        elif field in NUMERIC_FIELDS and parse_number(record[field]) is not None:
            checks.append(lambda v=record[field]: numeric_match(msg, v))
        else:
            checks.append(lambda e=expected: e in m)
    if gaps == len(pairs):
        return any(p in msg.lower() for p in GAP_PHRASES), True
    return all(check() for check in checks), False


_HOLDING = re.compile(r"\s*([^()?]{1,100}?)\s*\((\d+(?:\.\d+)?)%\)\s*(?:,\s*)?")


def parse_holdings(text) -> Optional[List[Tuple[str, float]]]:
    """'A Ltd(5.1%), B(4%)' -> [('A Ltd', 5.1), ('B', 4.0)]; None if the text is not purely such a list."""
    if not isinstance(text, str) or not text.strip() or text.strip() == "N/A":
        return None
    items, pos = [], 0
    while pos < len(text):
        m = _HOLDING.match(text, pos)
        if not m:
            return None
        items.append((m.group(1).strip(), float(m.group(2))))
        pos = m.end()
    return items or None


def holdings_ok(msg: str, items: List[Tuple[str, float]]) -> bool:
    """Every holding named in the answer, with its percentage matching numerically."""
    m = norm(msg)
    return all(norm(name) in m and any(abs(n - pct) <= 0.005 for n in numbers_in(msg)) for name, pct in items)


def daily_na_ok(msg: str) -> bool:
    """An honest 'not available' that gives no daily-change figure and no 0.0 placeholder."""
    says_missing = any(p in msg.lower() for p in GAP_PHRASES)
    has_percent_figure = re.search(r"[-\u2212\u2013]?\d+(?:\.\d+)?\s*%", msg) is not None
    has_zero_placeholder = re.search(r"(?<![\d.])0\.0+(?!\d)", msg) is not None
    return says_missing and not has_percent_figure and not has_zero_placeholder


# ---------------------------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_summary(repo: Path) -> str:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return "git: not a git repository"
    commit = _git(repo, "rev-parse", "--short", "HEAD") or "?"
    lines = (_git(repo, "status", "--porcelain") or "").splitlines()
    untracked = sum(1 for ln in lines if ln.startswith("??"))
    tracked = len(lines) - untracked
    tree = f"dirty ({tracked} tracked changed, {untracked} untracked)" if lines else "clean"
    return f"git: branch {branch} | commit {commit} | working tree {tree}"


def chroma_fund_names(repo: Path) -> Optional[Dict[str, str]]:
    """fund_id -> fund_name stored in the Chroma index, read straight from its sqlite file, read-only."""
    path = repo / "phase_1" / "data" / "chroma" / "chroma.sqlite3"
    if not path.exists():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute(
            "SELECT id, key, string_value FROM embedding_metadata WHERE key IN ('fund_id', 'fund_name')"
        ).fetchall()
    finally:
        con.close()
    by_id: Dict[int, Dict[str, str]] = {}
    for rid, key, value in rows:
        by_id.setdefault(rid, {})[key] = value
    return {d["fund_id"]: d["fund_name"] for d in by_id.values() if "fund_id" in d and "fund_name" in d}


def run_preflight(repo: Path, now: Optional[datetime] = None) -> Tuple[List[str], List[str]]:
    """Returns (info lines, problems). Problems are what an online run must not start with."""
    now = now or datetime.now(timezone.utc)
    info = [git_summary(repo)]
    problems: List[str] = []

    funds_path = repo / "phase_1" / "data" / "funds.json"
    funds = json.loads(funds_path.read_text())["funds"]
    stamps = [f["scraped_at"] for f in funds if f.get("scraped_at")]
    if stamps:
        latest = max(stamps)
        age = (now - datetime.fromisoformat(latest.replace("Z", "+00:00"))).total_seconds() / 3600
        info.append(f"funds.json: {len(funds)} funds | latest scrape {latest} ({age:.1f} h old)")
        if age > MAX_AGE_HOURS:
            problems.append(f"funds.json is {age:.1f} h old (limit {MAX_AGE_HOURS} h)")
    else:
        info.append(f"funds.json: {len(funds)} funds | no scrape timestamps")
        problems.append("funds.json has no scrape timestamps, so its age is unknown")

    funds_names = {f["fund_id"]: f["fund_name"] for f in funds}
    registry = json.loads((repo / "phase_0" / "data" / "source_registry.json").read_text())
    registry_names = {s["fund_id"]: s["fund_name"] for s in registry["sources"]}
    diffs = [
        f"{fid}: funds.json {funds_names.get(fid)!r} vs registry {registry_names.get(fid)!r}"
        for fid in sorted(set(funds_names) | set(registry_names))
        if funds_names.get(fid) != registry_names.get(fid)
    ]
    info.append("names, funds.json vs registry: " + ("all match" if not diffs else f"{len(diffs)} differ"))
    problems += [f"fund name differs from the registry: {d}" for d in diffs]

    try:
        chroma = chroma_fund_names(repo)
    except Exception as e:  # unreadable store
        chroma, problems = None, problems + [f"Chroma index could not be read: {e}"]
    else:
        if chroma is None:
            problems.append("Chroma index not found")
    if chroma is not None:
        cdiffs = [
            f"{fid}: funds.json {funds_names.get(fid)!r} vs Chroma {chroma.get(fid)!r}"
            for fid in sorted(set(funds_names) | set(chroma))
            if funds_names.get(fid) != chroma.get(fid)
        ]
        info.append("names, Chroma vs funds.json: " + ("all match" if not cdiffs else f"{len(cdiffs)} differ"))
        problems += [f"fund name in the Chroma index differs from funds.json: {d}" for d in cdiffs]
    return info, problems


def preflight(repo: Path, offline: bool, allow_stale: bool, out: Callable[[str], None] = print,
              now: Optional[datetime] = None) -> bool:
    """Print the preflight. Returns False when an online run must stop."""
    out("== Preflight ==")
    try:
        info, problems = run_preflight(repo, now)
    except Exception as e:
        info, problems = [], [f"preflight could not read the data files: {type(e).__name__}: {e}"]
    for line in info:
        out("  " + line)
    if not problems:
        out("  all checks passed")
        return True
    if offline:
        for p in problems:
            out(f"  WARNING: {p}")
        out("  (--offline: continuing; the local data is deliberately old)")
        return True
    if allow_stale:
        for p in problems:
            out(f"  WARNING (bypassed by --allow-stale): {p}")
        return True
    for p in problems:
        out(f"  STOP: {p}")
    out("  The online run was not started. Refresh the data (daily update) or re-run with --allow-stale.")
    return False
