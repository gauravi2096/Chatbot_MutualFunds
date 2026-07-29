"""
Unit tests for fund detection and ambiguous fund clarification in "All funds" mode.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_2.fund_detection import detect_funds_in_query
from phase_2.orchestration import chat


def test_fund_detection():
    # 0 funds
    assert detect_funds_in_query("What's the expense ratio?") == []
    assert detect_funds_in_query("What's the risk level?") == []
    assert detect_funds_in_query("Compare expense ratios of two funds") == []

    # 1 fund (exact / alias / partial)
    assert len(detect_funds_in_query("What is the NAV of HDFC Flexi Cap Fund?")) == 1
    assert detect_funds_in_query("What is the NAV of HDFC Flexi Cap Fund?")[0] == "hdfc-flexi-cap-fund-direct-plan-growth-option-3184"
    assert len(detect_funds_in_query("flexi cap expense ratio")) == 1
    assert len(detect_funds_in_query("small cap returns")) == 1
    assert len(detect_funds_in_query("infrastructure fund AUM")) == 1
    assert len(detect_funds_in_query("gold etf returns")) == 1
    assert len(detect_funds_in_query("mid cap NAV")) == 1

    # 2 funds (comparison)
    res_2 = detect_funds_in_query("Compare HDFC Flexi Cap Fund and HDFC Small Cap Fund")
    assert len(res_2) == 2
    assert "hdfc-flexi-cap-fund-direct-plan-growth-option-3184" in res_2
    assert "hdfc-small-cap-fund-direct-growth-option-3580" in res_2

    print("PASS: test_fund_detection")


def test_ambiguous_query_chat():
    # In "All funds" mode (fund_id=None), generic query with 0 funds should return needs_fund_clarification=True
    res = chat(query="What's the expense ratio?", fund_id=None)
    assert res.get("needs_fund_clarification") is True
    assert "Which fund would you like to know about?" in res.get("message", "")

    # Restricted query in "All funds" mode should NOT request fund clarification, but return redirect
    res_adv = chat(query="Which fund should I invest in?", fund_id=None)
    assert res_adv.get("needs_fund_clarification") is not True
    assert res_adv.get("rejected") is True

    # Query with 1 fund mentioned in "All funds" mode should scope and retrieve, not request clarification
    res_single = chat(query="What is the expense ratio of HDFC Flexi Cap Fund?", fund_id=None)
    assert res_single.get("needs_fund_clarification") is not True

    print("PASS: test_ambiguous_query_chat")


if __name__ == "__main__":
    test_fund_detection()
    test_ambiguous_query_chat()
    print("\nAll unit tests passed successfully!")
