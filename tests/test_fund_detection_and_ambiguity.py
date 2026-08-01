"""
Unit tests for intent classification, fund detection, and conversational name capture.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_2.fund_detection import detect_funds_in_query
from phase_2.orchestration import chat
from streamlit_app import classify_name_response, extract_name_from_text


def test_intent_classification():
    # Intent 1: Greeting/Chitchat -> no retrieval, no fund clarification
    greetings = ["hi", "hello", "thanks", "thank you", "good morning", "bye"]
    for g in greetings:
        res = chat(query=g, fund_id=None)
        assert res.get("is_greeting") is True, f"Failed greeting check for {g}"
        assert res.get("needs_fund_clarification") is False
        assert "Hi!" in res.get("message", "")

    # Intent 2: Advisory / Opinion -> AMFI redirect, rejected=True
    res_adv = chat(query="Which fund should I invest in for best returns?", fund_id=None)
    assert res_adv.get("rejected") is True
    assert res_adv.get("needs_fund_clarification") is not True

    # Intent 3: Factual query, 0 funds named in All funds mode -> needs_fund_clarification=True
    res_zero = chat(query="What's the expense ratio?", fund_id=None)
    assert res_zero.get("needs_fund_clarification") is True

    # Intent 4: Factual query, 1 fund named -> single fund retrieval
    res_one = chat(query="What is the expense ratio of HDFC Flexi Cap Fund?", fund_id=None)
    assert res_one.get("needs_fund_clarification") is not True
    assert res_one.get("rejected") is False

    # Intent 5: Factual query, 2+ funds named -> comparison flow
    res_two = chat(query="Compare expense ratios of HDFC Flexi Cap Fund and HDFC Small Cap Fund", fund_id=None)
    assert res_two.get("needs_fund_clarification") is not True

    print("PASS: test_intent_classification")


def test_name_capture_helpers():
    # Skip inputs
    assert classify_name_response("no thanks") == "skip"
    assert classify_name_response("skip") == "skip"
    assert classify_name_response("no") == "skip"
    assert classify_name_response("nope") == "skip"

    # Name inputs
    assert classify_name_response("Gauravi") == "name"
    assert classify_name_response("Alex") == "name"
    assert classify_name_response("Call me Gauravi") == "name"
    assert classify_name_response("my name is Sam") == "name"

    # Real questions / advice
    assert classify_name_response("What is the NAV of HDFC Flexi Cap?") == "question"
    assert classify_name_response("Which fund is best to invest in?") == "question"

    # Name extraction
    assert extract_name_from_text("Gauravi") == "Gauravi"
    assert extract_name_from_text("my name is gauravi") == "Gauravi"
    assert extract_name_from_text("call me Alex") == "Alex"

    print("PASS: test_name_capture_helpers")


if __name__ == "__main__":
    test_intent_classification()
    test_name_capture_helpers()
    print("\nAll intent classification & name capture tests passed!")
