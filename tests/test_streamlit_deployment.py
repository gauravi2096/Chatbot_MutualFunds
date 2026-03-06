"""
Test the deployed Streamlit backend at chatbot-for-mutualfunds.streamlit.app.

Run: python tests/test_streamlit_deployment.py
Override URL: STREAMLIT_APP_URL=https://your-app.streamlit.app python tests/test_streamlit_deployment.py

Prints PASS or FAIL for each test. Uses HTTP GET only (no browser automation).
"""

import os
import sys

try:
    import requests
except ImportError:
    print("FAIL: install requests: pip install requests")
    sys.exit(1)

STREAMLIT_APP_URL = os.environ.get(
    "STREAMLIT_APP_URL",
    "https://chatbot-for-mutualfunds.streamlit.app/",
).rstrip("/")
TIMEOUT = 30


def run_test(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    msg = f"  {status}: {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def main() -> int:
    print(f"Testing deployed Streamlit app: {STREAMLIT_APP_URL}\n")

    failures = 0

    # Test 1: App URL returns HTTP 200
    try:
        resp = requests.get(STREAMLIT_APP_URL, timeout=TIMEOUT, allow_redirects=True)
        run_test("App URL returns 200", resp.status_code == 200, f"got {resp.status_code}")
        if resp.status_code != 200:
            failures += 1
    except requests.RequestException as e:
        run_test("App URL returns 200", False, str(e))
        failures += 1
        print("\nCannot continue without a successful GET.")
        return 1

    text = resp.text

    # Test 2: Page contains Streamlit (confirms Streamlit shell loaded)
    run_test(
        "Page is served by Streamlit",
        "streamlit" in text.lower(),
        "expected 'streamlit' in response body",
    )
    if "streamlit" not in text.lower():
        failures += 1

    # Test 3: Page contains app title or key UI text (optional: Streamlit often loads content via JS)
    has_app_marker = (
        "indmoney" in text.lower()
        or "fund chat" in text.lower()
        or "select a fund" in text.lower()
        or ("fund" in text.lower() and "chat" in text.lower())
    )
    run_test(
        "Page contains app content (INDmoney / Fund Chat / Select a fund)",
        has_app_marker,
        "expected app identifier in response" if not has_app_marker else "",
    )
    # Do not count as failure: initial HTML may not include app text when content loads dynamically

    # Test 4: No server error in body (e.g. 500 message)
    no_error = "internal server error" not in text.lower() and "500" not in text[:500]
    run_test("Page does not show server error", no_error, "no 500 or internal error in body")
    if not no_error:
        failures += 1

    # Test 5: Content-Type suggests HTML
    content_type = resp.headers.get("Content-Type", "")
    is_html = "text/html" in content_type
    run_test("Response is HTML", is_html, f"Content-Type: {content_type}")
    if not is_html:
        failures += 1

    print()
    if failures:
        print(f"Result: {failures} required test(s) FAILED")
        return 1
    print("Result: All required tests PASSED (deployed app is reachable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
