"""
Offline tests (no network, no Chroma): the funds renamed to match the source site are detected
under both their old and their new names, and the registry carries the new names.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_0.source_registry import PHASE_1_SOURCES
from phase_1.config import REGISTRY_PATH
from phase_2.fund_detection import detect_funds_in_query

# fund_id -> (old name, new name). The fund_id and URL never change.
RENAMED = {
    "hdfc-dynamic-debt-plan-direct-plan-growth-option-513": ("HDFC Dynamic Debt Fund", "HDFC Dynamic Term Fund"),
    "hdfc-low-duration-direct-plan-growth-option-1481": ("HDFC Low Duration", "HDFC Ultra Short to Short Term Fund"),
    "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359": ("HDFC Gold ETF FoF", "HDFC Gold ETF Fund of Fund"),
    "hdfc-hybrid-equity-fund-direct-growth-option-4103": ("HDFC Hybrid Equity Fund", "HDFC Aggressive Hybrid Fund"),
}
# Extra spellings that must keep working (old short forms) or newly work (new short forms).
EXTRA_ALIASES = {
    "hdfc-dynamic-debt-plan-direct-plan-growth-option-513": ["dynamic debt", "dynamic term fund", "dynamic term"],
    "hdfc-low-duration-direct-plan-growth-option-1481": ["low duration", "ultra short to short term", "ultra short"],
    "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359": ["gold etf fof", "gold fof", "gold etf", "gold fund", "gold etfs"],  # bare "gold" and bare "fund of fund" detect nothing
    "hdfc-hybrid-equity-fund-direct-growth-option-4103": ["hybrid equity", "aggressive hybrid fund", "aggressive hybrid"],
}


def test_old_and_new_name_detect_the_same_fund_id():
    for fund_id, (old, new) in RENAMED.items():
        for name in (old, new):
            assert detect_funds_in_query(name) == [fund_id], (name, detect_funds_in_query(name))
            for template in ("What is the NAV of {}?", "what is the expense ratio of {}", "{} exit load"):
                q = template.format(name)
                assert detect_funds_in_query(q) == [fund_id], (q, detect_funds_in_query(q))
            # without the "HDFC" prefix and in lower case
            bare = name.lower().removeprefix("hdfc ") if hasattr(str, "removeprefix") else name.lower()[5:]
            assert detect_funds_in_query(f"nav of {bare}") == [fund_id], bare


def test_extra_aliases_detect_the_same_fund():
    for fund_id, aliases in EXTRA_ALIASES.items():
        for alias in aliases:
            assert detect_funds_in_query(f"What is the AUM of {alias}?") == [fund_id], alias


def test_old_and_new_names_in_one_query_do_not_double_count():
    for fund_id, (old, new) in RENAMED.items():
        assert detect_funds_in_query(f"{old} is now called {new}") == [fund_id]


def test_comparing_a_renamed_fund_with_another_returns_both_in_order():
    ids = detect_funds_in_query("Compare HDFC Hybrid Equity Fund and HDFC Mid Cap Fund")
    assert ids == ["hdfc-hybrid-equity-fund-direct-growth-option-4103", "hdfc-mid-cap-fund-direct-plan-growth-option-3097"], ids
    ids = detect_funds_in_query("Compare HDFC Mid Cap Fund and HDFC Aggressive Hybrid Fund")
    assert ids == ["hdfc-mid-cap-fund-direct-plan-growth-option-3097", "hdfc-hybrid-equity-fund-direct-growth-option-4103"], ids


def test_registry_python_and_json_carry_the_new_names_and_unchanged_ids():
    py = dict(PHASE_1_SOURCES)
    js = {s["fund_id"]: s["fund_name"] for s in json.loads(Path(REGISTRY_PATH).read_text())["sources"]}
    assert len(py) == 10 and set(py) == set(js)
    for fund_id, (old, new) in RENAMED.items():
        assert py[fund_id] == new and js[fund_id] == new, (fund_id, py[fund_id], js[fund_id])
    # every fund name in the registry detects its own fund_id
    for fund_id, name in py.items():
        assert detect_funds_in_query(name) == [fund_id], name


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
