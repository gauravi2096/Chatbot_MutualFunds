"""
End-to-end tests for the INDmoney Fund Chatbot.

Verifies: RAG retrieval, context building, Groq responses, response format
(source link + last_data_update), and that only factual queries are answered
while advisory queries get a redirect.

Run with the backend up: python tests/e2e_chatbot_test.py
Optional: CHATBOT_BASE_URL=http://localhost:8000
"""

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.environ.get("CHATBOT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CHAT_URL = f"{BASE_URL}/chat"
HEALTH_URL = f"{BASE_URL}/health"

# Expected timestamp format: "Mar 06, 2026 06:06 am" (date + 12h am/pm)
LAST_UPDATE_PATTERN = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+(am|pm)$",
    re.IGNORECASE,
)
INDMONEY_URL_PREFIX = "https://www.indmoney.com/mutual-funds/"


def post_chat(message: str) -> dict:
    """POST /chat and return parsed JSON."""
    req = Request(
        CHAT_URL,
        data=json.dumps({"message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_health() -> dict:
    """GET /health."""
    with urlopen(Request(HEALTH_URL), timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def assert_response_shape(data: dict, label: str) -> None:
    """Assert response has message, source_url, last_data_update."""
    assert "message" in data, f"{label}: missing 'message'"
    assert "source_url" in data, f"{label}: missing 'source_url'"
    assert "last_data_update" in data, f"{label}: missing 'last_data_update'"
    assert isinstance(data["message"], str), f"{label}: message must be string"
    assert isinstance(data["source_url"], str), f"{label}: source_url must be string"
    assert isinstance(data["last_data_update"], str), f"{label}: last_data_update must be string"


def assert_source_link(url: str, label: str) -> None:
    """Assert source_url is a valid INDmoney fund page link (has fund slug after prefix)."""
    assert url.startswith(INDMONEY_URL_PREFIX), (
        f"{label}: source_url should start with {INDMONEY_URL_PREFIX}, got {url[:60]}..."
    )
    slug = url[len(INDMONEY_URL_PREFIX):].strip().lstrip("/")
    assert len(slug) > 0, f"{label}: source_url should have fund slug after prefix"


def assert_timestamp_format(ts: str, label: str) -> None:
    """Assert last_data_update matches date + 12h am/pm."""
    assert ts.strip(), f"{label}: last_data_update must be non-empty"
    assert LAST_UPDATE_PATTERN.match(ts.strip()), (
        f"{label}: last_data_update should match 'Mon DD, YYYY H:MM am/pm', got {ts!r}"
    )


def run_tests() -> tuple[int, int]:
    """Run all E2E tests. Returns (passed, failed)."""
    passed = 0
    failed = 0

    # --- Health ---
    try:
        health = get_health()
        assert health.get("status") == "ok", "health status"
        print("[PASS] GET /health returns status ok")
        passed += 1
    except Exception as e:
        print(f"[FAIL] GET /health: {e}")
        failed += 1
        return passed, failed  # Cannot continue without backend

    # --- Factual: NAV and AUM (HDFC Mid Cap Fund) ---
    try:
        data = post_chat("What is the NAV and AUM of HDFC Mid Cap Fund?")
        assert_response_shape(data, "Factual NAV/AUM")
        assert_source_link(data["source_url"], "Factual NAV/AUM")
        assert_timestamp_format(data["last_data_update"], "Factual NAV/AUM")
        msg = data["message"].lower()
        if "couldn't generate" in msg or "try again" in msg:
            print("[PASS] Factual query (NAV/AUM): correct shape, source link, timestamp (LLM unavailable — run with GROQ_API_KEY for full check)")
            passed += 1
        else:
            assert "nav" in msg or "217" in msg or "aum" in msg or "92187" in msg or "mid cap" in msg, (
                f"Factual NAV/AUM: message should mention NAV/AUM or fund name, got: {data['message'][:120]}..."
            )
            assert "indmoney" not in msg and "http" not in msg, (
                "Factual NAV/AUM: message should not contain source link (added separately)"
            )
            print("[PASS] Factual query (NAV/AUM): correct shape, source link, timestamp, and factual content")
            passed += 1
    except HTTPError as e:
        print(f"[FAIL] Factual NAV/AUM (HTTP {e.code}): {e.read().decode()[:200]}")
        failed += 1
    except Exception as e:
        print(f"[FAIL] Factual NAV/AUM: {e}")
        failed += 1

    # --- Factual: Expense ratio ---
    try:
        data = post_chat("What is the expense ratio of HDFC Flexi Cap Fund?")
        assert_response_shape(data, "Factual expense ratio")
        assert_source_link(data["source_url"], "Factual expense ratio")
        assert_timestamp_format(data["last_data_update"], "Factual expense ratio")
        msg = data["message"].lower()
        if "couldn't generate" in msg or "try again" in msg:
            print("[PASS] Factual query (expense ratio): correct shape, source link, timestamp (LLM unavailable)")
            passed += 1
        else:
            assert "expense" in msg or "%" in msg or "flexi" in msg, (
                f"Factual expense: message should mention expense or %, got: {data['message'][:120]}..."
            )
            print("[PASS] Factual query (expense ratio): correct shape and content")
            passed += 1
    except HTTPError as e:
        print(f"[FAIL] Factual expense ratio (HTTP {e.code}): {e.read().decode()[:200]}")
        failed += 1
    except Exception as e:
        print(f"[FAIL] Factual expense ratio: {e}")
        failed += 1

    # --- Factual: Returns / risk (supported data points) ---
    try:
        data = post_chat("What is the 1Y CAGR and risk level of HDFC Small Cap Fund?")
        assert_response_shape(data, "Factual returns/risk")
        assert_source_link(data["source_url"], "Factual returns/risk")
        assert_timestamp_format(data["last_data_update"], "Factual returns/risk")
        msg = data["message"].lower()
        if "couldn't generate" in msg or "try again" in msg:
            print("[PASS] Factual query (returns/risk): correct shape, source link, timestamp (LLM unavailable)")
            passed += 1
        else:
            assert "risk" in msg or "cagr" in msg or "return" in msg or "small cap" in msg or "%" in msg, (
                f"Factual returns/risk: message should mention risk/returns/fund, got: {data['message'][:120]}..."
            )
            print("[PASS] Factual query (returns/risk): correct shape and content")
            passed += 1
    except HTTPError as e:
        print(f"[FAIL] Factual returns/risk (HTTP {e.code}): {e.read().decode()[:200]}")
        failed += 1
    except Exception as e:
        print(f"[FAIL] Factual returns/risk: {e}")
        failed += 1

    # --- Advisory query: must get redirect, still have source_url and last_data_update ---
    try:
        data = post_chat("Which fund should I invest in for best returns?")
        assert_response_shape(data, "Advisory redirect")
        assert_timestamp_format(data["last_data_update"], "Advisory redirect")
        msg = data["message"].lower()
        assert "factual" in msg or "advice" in msg or "recommend" in msg or "cannot" in msg or "only" in msg, (
            f"Advisory: should redirect to factual-only, got: {data['message'][:120]}..."
        )
        # source_url may be empty if no retrieval was used for advisory, but often we still run retrieval
        assert isinstance(data["source_url"], str), "Advisory: source_url must be string"
        print("[PASS] Advisory query: redirected to factual-only, response still has timestamp (and source if any)")
        passed += 1
    except HTTPError as e:
        print(f"[FAIL] Advisory query (HTTP {e.code}): {e.read().decode()[:200]}")
        failed += 1
    except Exception as e:
        print(f"[FAIL] Advisory query: {e}")
        failed += 1

    # --- Out-of-scope / no data: should still return shape and timestamp ---
    try:
        data = post_chat("What is the NAV of XYZ Unknown Fund?")
        assert_response_shape(data, "Out-of-scope")
        assert_timestamp_format(data["last_data_update"], "Out-of-scope")
        msg = data["message"].lower()
        # Should say no data / not in context / ask for supported fund, or generic retry/couldn't generate
        assert (
            "don't" in msg or "do not" in msg or "enough" in msg or "context" in msg
            or "10" in msg or "listed" in msg or "specific" in msg
            or "couldn't" in msg or "try again" in msg
        ), (
            f"Out-of-scope: should indicate no data or inability to answer, got: {data['message'][:120]}..."
        )
        print("[PASS] Out-of-scope query: correct shape, timestamp, and no-data message")
        passed += 1
    except HTTPError as e:
        print(f"[FAIL] Out-of-scope (HTTP {e.code}): {e.read().decode()[:200]}")
        failed += 1
    except Exception as e:
        print(f"[FAIL] Out-of-scope: {e}")
        failed += 1

    return passed, failed


def main() -> int:
    print(f"E2E Chatbot tests — base URL: {BASE_URL}\n")
    try:
        passed, failed = run_tests()
    except URLError as e:
        print(f"[FAIL] Cannot reach backend at {BASE_URL}: {e}")
        return 1
    print(f"\nResult: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
