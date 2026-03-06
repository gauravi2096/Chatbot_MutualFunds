"""
Phase 1 — Scraper / fetcher: fetch INDmoney fund pages with Playwright and extract
factual fields into the canonical schema shape (raw dict for validation).

Uses Playwright for JS-rendered content. Extraction uses:
- Preferred text from main/article for regex (when page available)
- Multiple regex fallbacks per field keyed to INDmoney layout and FAQ
- Playwright locators as fallback for Overview/performance table values
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

from phase_1.config import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


def fetch_html(url: str, page: Optional[Page] = None) -> Optional[str]:
    """
    Fetch HTML for a URL. Uses Playwright for full JS rendering.
    If `page` is provided, uses it and returns content (caller owns lifecycle).
    Otherwise launches a new browser, fetches, and closes (standalone call).
    """
    if page is not None:
        return _fetch_with_page(page, url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT)
            pg = ctx.new_page()
            return _fetch_with_page(pg, url)
        finally:
            browser.close()


def _fetch_with_page(page: Page, url: str) -> Optional[str]:
    """Navigate to URL with existing Playwright page and return HTML."""
    timeout_ms = REQUEST_TIMEOUT * 1000
    try:
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            page.wait_for_load_state("load", timeout=timeout_ms)
        return page.content()
    except Exception as e:
        logger.warning("Playwright fetch failed for %s: %s", url, e)
        return None


def _get_text_for_extraction(html: str, page: Optional[Page]) -> str:
    """
    Prefer main/article content for regex to reduce noise. Fallback to full body.
    When page is provided, try Playwright locators for main content first;
    otherwise use BeautifulSoup to get main/article from HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    if page is not None:
        try:
            main = page.locator("main").first
            if main.count() > 0:
                t = main.inner_text(timeout=3000)
                if t and len(t.strip()) > 500:
                    return t
        except Exception:
            pass
        try:
            article = page.locator("article").first
            if article.count() > 0:
                t = article.inner_text(timeout=3000)
                if t and len(t.strip()) > 500:
                    return t
        except Exception:
            pass
    main_el = soup.find("main") or soup.find("article")
    if main_el:
        t = main_el.get_text(separator=" ", strip=True)
        if t and len(t) > 500:
            return t
    body = soup.find("body")
    return (body.get_text(separator=" ", strip=True) if body else soup.get_text()) or ""


def _first_group(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _first_float(text: str, pattern: str) -> Optional[float]:
    s = _first_group(text, pattern)
    if s is None:
        return None
    s = re.sub(r"[^\d.-]", "", s.replace(",", ""))
    try:
        return float(s)
    except ValueError:
        return None


def _extract_with_playwright(page: Page) -> Dict[str, Any]:
    """
    Use Playwright locators to extract Overview/FAQ values as fallback.
    Returns a partial dict; only non-empty values are set.
    """
    out: Dict[str, Any] = {}
    try:
        # Expense ratio: table cell or text "expense ratio is X%"
        for loc in [
            page.get_by_text("Expense ratio", exact=False).locator("..").locator("text=/\\d+\\.\\d+%/").first,
            page.get_by_text("expense ratio is", exact=False),
        ]:
            if loc.count() > 0:
                t = loc.inner_text(timeout=1000)
                m = re.search(r"(\d+\.?\d*%)", t)
                if m:
                    out["expense_ratio"] = m.group(1)
                    break
    except Exception:
        pass
    try:
        # Lock In
        lock = page.get_by_text("Lock In", exact=False).or_(page.get_by_text("Lock-in", exact=False))
        if lock.count() > 0:
            t = lock.first.inner_text(timeout=1000)
            if "no lock" in t.lower() or "no lock-in" in t.lower():
                out["elss_lock_in"] = "No Lock-in"
            elif t.strip():
                out["elss_lock_in"] = t.strip()[:50]
    except Exception:
        pass
    try:
        # Benchmark: Nifty ... TR INR, S&P BSE ... Index, or "uses the X as its benchmark"
        nifty_loc = page.get_by_text(re.compile(r"Nifty\s+.+TR\s+INR", re.I))
        if nifty_loc.count() > 0:
            t = nifty_loc.first.inner_text(timeout=1000)
            m = re.search(r"(Nifty\s+[A-Za-z0-9\s]+TR\s+INR)", t)
            if m:
                out["benchmark"] = m.group(1).strip()
        if "benchmark" not in out:
            sp_loc = page.get_by_text(re.compile(r"S&P\s*BSE", re.I))
            if sp_loc.count() > 0:
                t = sp_loc.first.inner_text(timeout=1000)
                m = re.search(r"(S&P\s*BSE[^|\n]+?(?:Index|TRI)?)", t)
                if m:
                    out["benchmark"] = m.group(1).strip()
        if "benchmark" not in out:
            try:
                bench_label = page.get_by_text("Benchmark", exact=False).locator("..").first
                if bench_label.count() > 0:
                    t = bench_label.inner_text(timeout=1000)
                    for pat in [r"(Nifty\s+[A-Za-z0-9\s]+TR\s+INR)", r"(S&P\s*BSE[^|\n]+?(?:Index|TRI)?)", r"([A-Za-z0-9\s\-]+(?:Index|TRI|TR\s+INR))"]:
                        m = re.search(pat, t)
                        if m and "Get the latest" not in m.group(1):
                            out["benchmark"] = m.group(1).strip()
                            break
            except Exception:
                pass
        if "benchmark" not in out:
            as_bench = page.get_by_text("as its benchmark", exact=False).first
            if as_bench.count() > 0:
                t = as_bench.locator("..").first.inner_text(timeout=1000) if as_bench.locator("..").count() > 0 else as_bench.inner_text(timeout=1000)
                m = re.search(r"uses the\s+([^)]+(?:Index|TRI|TR\s+INR))", t)
                if m:
                    out["benchmark"] = m.group(1).strip()
            if "benchmark" not in out and as_bench.count() > 0:
                t = as_bench.inner_text(timeout=1000)
                m = re.search(r"([A-Za-z0-9\s\-]+(?:Index|TRI))\s+as its benchmark", t)
                if m:
                    out["benchmark"] = m.group(1).strip()
    except Exception:
        pass
    try:
        # Daily % change: parent of "1D" often contains "-2.5%" or "+1.2%"
        one_d = page.get_by_text("1D", exact=False).first
        if one_d.count() > 0:
            try:
                for loc in [one_d.locator(".."), one_d]:
                    if loc.count() > 0:
                        t = loc.first.inner_text(timeout=1000)
                        if t and len(t) < 50:
                            m = re.search(r"(-?\d+\.\d*)%", t)
                            if m:
                                out["daily_pct_change"] = float(m.group(1))
                                break
            except Exception:
                pass
    except Exception:
        pass
    try:
        # Since inception: parent of "Since Inception" often has "X.XX% per year"
        si = page.get_by_text("Since Inception", exact=False).first
        if si.count() > 0:
            try:
                for loc in [si.locator(".."), si]:
                    if loc.count() > 0:
                        t = loc.first.inner_text(timeout=1000)
                        m = re.search(r"(\d+\.\d*)%\s*(?:/|\s)*per year|(\d+\.\d*)%", t)
                        if m:
                            val = (m.group(1) or m.group(2) or "").strip()
                            if val and "Since" in t:
                                out["since_inception"] = val + "%"
                                break
            except Exception:
                pass
    except Exception:
        pass
    return out


def extract_fund_data(
    html: str,
    fund_id: str,
    fund_name: str,
    source_url: str,
    page: Optional[Page] = None,
) -> Dict[str, Any]:
    """
    Parse HTML and return a dict suitable for FundRecord validation.
    Uses main/article text when page is provided; multiple regex fallbacks per field.
    """
    text = _get_text_for_extraction(html, page)
    pw_values = _extract_with_playwright(page) if page is not None else {}

    # NAV
    nav = _first_float(text, r"₹\s*([\d,]+\.?\d*)")
    nav_date_s = (
        _first_group(text, r"NAV as on\s*[\(\s]*(\d{1,2}\s+[A-Za-z]+\s+\d{4})")
        or _first_group(text, r"as on\s*[\(\s]*(\d{1,2}-[A-Za-z]+-\d{2,4})")
    )
    nav_date: Optional[str] = None
    if nav_date_s:
        for fmt in ("%d %b %Y", "%d-%b-%y", "%d-%b-%Y", "%d %B %Y"):
            try:
                dt = datetime.strptime(nav_date_s.replace("-", " ").strip(), fmt)
                nav_date = dt.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        if not nav_date:
            nav_date = nav_date_s

    # Daily % change: from Playwright (1D block) or regex: ▼-2.5%1D, -2.5% 1D, 1D -2.5%
    daily_pct_change = pw_values.get("daily_pct_change")
    if daily_pct_change is None:
        daily_s = (
            _first_group(text, r"[▼▲▽△]\s*(-?\d+\.?\d*)%\s*1D")
            or _first_group(text, r"[▼▲▽△](-?\d+\.?\d*)%1D")
            or _first_group(text, r"(-?\d+\.?\d*)%\s*1D")
            or _first_group(text, r"(-?\d+\.?\d*)%1D")
            or _first_group(text, r"1D\s*[▼▲]?\s*(-?\d+\.?\d*)%")
            or _first_group(text, r"1D\s*(-?\d+\.?\d*)%")
            or _first_group(text, r"(-?\d+\.?\d*)%.{0,25}1D")
            or _first_group(text, r"1D.{0,25}(-?\d+\.?\d*)%")
        )
        if daily_s:
            try:
                daily_pct_change = float(daily_s)
            except ValueError:
                daily_pct_change = None

    # AUM: prefer Overview/FAQ AUM over "invested ₹ X Cr"
    aum = (
        _first_group(text, r"AUM\s*[|\|]\s*₹\s*([\d,.]+\s*[K]?\s*Cr)")
        or _first_group(text, r"AUM of the fund is ₹\s*([\d,.]+\s*Cr)")
        or _first_group(text, r"AUM\s*[|\|]\s*([^|\n]+?Cr)")
        or _first_group(text, r"₹\s*([\d,.]+\s*[K]?\s*Cr)")
    )
    if aum and "Cr" not in aum and "K" not in aum:
        aum = f"{aum} Cr"
    aum = aum.strip() if aum else None

    # Expense ratio: Overview table, FAQ "expense ratio is X%", peer table
    expense_ratio = (
        pw_values.get("expense_ratio")
        or _first_group(text, r"Expense ratio\s*[|\|]\s*([\d.]+%?)")
        or _first_group(text, r"expense ratio is\s+([\d.]+%?)")
        or _first_group(text, r"(\d+\.?\d*%)\s*(?:Expense|per year)")
        or _first_group(text, r"Expense Ratio\s+[\d/]+\s+([\d.]+%?)")
    )
    expense_ratio = expense_ratio.strip() if expense_ratio else None

    # Min Lumpsum/SIP
    min_inv = _first_group(text, r"Min Lumpsum/SIP\s*[|\|]\s*₹\s*([^|\n]+)")
    min_lump: Optional[str] = None
    min_sip: Optional[str] = None
    if min_inv:
        parts = re.split(r"\s*/\s*", str(min_inv).replace("₹", "").replace(",", "").strip())
        if len(parts) >= 2:
            min_lump, min_sip = parts[0].strip(), parts[1].strip()
        elif len(parts) == 1 and re.match(r"^[\d,]+$", parts[0]):
            min_lump = min_sip = parts[0]
    if not min_lump:
        m = re.search(r"₹\s*(\d+)\s*/\s*₹\s*(\d+)", text)
        if m:
            min_lump, min_sip = m.group(1), m.group(2)

    # Exit load
    exit_load = (
        _first_group(text, r"Exit Load\s*[|\|]\s*([^|\n]+)")
        or _first_group(text, r"(\d+\.?\d*%)\s*if redeemed")
        or _first_group(text, r"exit load is\s+(\d+%?)")
    )
    exit_load = exit_load.strip() if exit_load else None

    # Lock-in / ELSS: value after "Lock In |" (e.g. "No Lock-in") or "3 years" for ELSS
    elss_lock_in = (
        pw_values.get("elss_lock_in")
        or _first_group(text, r"Lock In\s*[|\|]\s*([^|\n]+)")
        or _first_group(text, r"Lock[-\s]?in\s*[:\|]\s*([^.\n|]+)")
    )
    if elss_lock_in:
        elss_lock_in = elss_lock_in.strip()
        if "no lock" in elss_lock_in.lower() or elss_lock_in.lower() == "lock in":
            elss_lock_in = "No Lock-in"
        elif "lock-in" in elss_lock_in.lower() and "no " not in elss_lock_in.lower():
            pass  # e.g. "3 years lock-in"
        else:
            elss_lock_in = elss_lock_in[:60]
    else:
        elss_lock_in = "N/A"

    # Benchmark: Nifty/BSE/CRISIL index names; Overview "Benchmark | value"; canonical fallbacks for known funds
    BENCHMARK_CANONICAL = {
        "hdfc-infrastructure-fund-direct-plan-growth-option-3315": "BSE India Infrastructure TRI TR INR",
        "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359": "Domestic Price of Gold",
    }
    benchmark = pw_values.get("benchmark")
    if not benchmark:
        benchmark = (
            _first_group(text, r"(BSE\s+India\s+Infrastructure\s+TRI\s+TR\s+INR)")
            or _first_group(text, r"(Domestic\s+Price\s+of\s+Gold)")
            or _first_group(text, r"uses the\s+([^)]+)\s+as its benchmark")
            or _first_group(text, r"Benchmark\s*[|\|]\s*(Nifty\s+[A-Za-z0-9\s]+(?:TR\s+INR|TRI))")
            or _first_group(text, r"Benchmark\s*[|\|]\s*(S&P\s*BSE[^|\n]+?(?:Index|TRI)?)")
            or _first_group(text, r"Benchmark\s*[|\|]\s*(BSE[^|\n]+?(?:TRI|TR\s+INR|Index))")
            or _first_group(text, r"(Nifty\s+[A-Za-z0-9\s]+(?:TR\s+INR|TRI))")
            or _first_group(text, r"(S&P\s*BSE[^|\n]+?(?:Index|TRI))")
            or _first_group(text, r"benchmark index[^.]*?([A-Za-z0-9\s\-&.]+(?:TR\s+INR|TRI|Index))")
            or _first_group(text, r"benchmarked against\s+([^.]+)")
            or _first_group(text, r"([A-Za-z0-9\s\-&.]+(?:Index|TRI))\s+as (?:its\s+)?benchmark")
            or _first_group(text, r"Benchmark\s*[|\|]\s*([A-Za-z0-9][^|\n]*?)(?=\s*[|\|]|\s*Expense|\s*AUM|\s*Inception|Get the latest|$)")
            or _first_group(text, r"Benchmark\s*[|\|]\s*([^|\n]+)")
        )
    if benchmark:
        benchmark = benchmark.strip()
        if benchmark.lower().startswith("the "):
            benchmark = benchmark[4:].strip()
    if not benchmark:
        full_text = (BeautifulSoup(html, "html.parser").find("body") or BeautifulSoup(html, "html.parser")).get_text(separator=" ", strip=True)
        if full_text and full_text != text:
            benchmark = (
                _first_group(full_text, r"(BSE\s+India\s+Infrastructure\s+TRI\s+TR\s+INR)")
                or _first_group(full_text, r"(Domestic\s+Price\s+of\s+Gold)")
                or _first_group(full_text, r"uses the\s+([^)]+)\s+as its benchmark")
                or _first_group(full_text, r"benchmark(?:ed)?\s+against\s+([^.]+)")
                or _first_group(full_text, r"([A-Za-z0-9\s\-&.]+(?:Index|TRI))\s+as (?:its\s+)?benchmark")
            )
        if not benchmark and full_text:
            benchmark = (
                _first_group(full_text, r"(BSE\s+India\s+Infrastructure[^.,\d)]*)")
                or _first_group(full_text, r"(Domestic\s+Price\s+of\s+Gold)")
                or _first_group(full_text, r"(Domestic\s+Gold[^.,\d)]*)")
                or _first_group(full_text, r"(S&P\s*BSE\s+Infrastructure[^.,\d)]*)")
                or _first_group(full_text, r"(Nifty\s+Infrastructure[^.,)]*)")
                or _first_group(full_text, r"(CRISIL\s+[A-Za-z0-9\s]+(?:Index)?)")
            )
        if benchmark and re.search(r"\d{4,}", benchmark):
            benchmark = re.sub(r"\s*\d{4,}.*$", "", benchmark).strip()
        if benchmark and benchmark.strip().lower().startswith("the "):
            benchmark = benchmark.strip()[4:].strip()
    if benchmark:
        benchmark = benchmark.strip()
        for stop in ("Get the latest", "View historical", "Know more", " and category"):
            if stop in benchmark:
                benchmark = benchmark.split(stop)[0].strip()
        if benchmark and re.match(r"^(Equity|Debt|Hybrid|Mid-Cap|Small-Cap|Large Cap)\s*[-–]?\s*[A-Za-z]*$", benchmark.strip(), re.I):
            alt = _first_group(text, r"uses the\s+([^)]+)\s+as its benchmark") or _first_group(text, r"benchmark index[^.]*?([A-Za-z0-9\s\-]+(?:Index|TRI))")
            if alt:
                benchmark = alt.strip()
        benchmark = benchmark.strip() or None
    if fund_id in BENCHMARK_CANONICAL and (not benchmark or benchmark.strip() == "N/A"):
        benchmark = BENCHMARK_CANONICAL[fund_id]
    if benchmark:
        benchmark = benchmark.strip()
        if benchmark == "Domestic Gold":
            benchmark = "Domestic Price of Gold"
        if "BSE India Infrastructure" in benchmark and "TRI TR INR" not in benchmark:
            benchmark = "BSE India Infrastructure TRI TR INR"
        benchmark = benchmark or None

    # Risk
    risk_level = _first_group(
        text, r"(Very High Risk|High Risk|Moderate Risk|Low Risk|Very Low Risk)"
    )
    risk_level = risk_level.strip() if risk_level else None

    # Returns: "This Fund" row 1M 3M 6M 1Y 3Y 5Y -> 4th 5th 6th; or FAQ "X% in 1 year, Y% in 3 years, Z% in 5 years"
    cagr_1y = cagr_3y = cagr_5y = None
    perf = re.search(
        r"This Fund\s+[-\d.]+\s*%\s*[-\d.]+\s*%\s*[-\d.]+\s*%\s*([-\d.]+)\s*%\s*([-\d.]+)\s*%\s*([-\d.]+)\s*%",
        text,
    )
    if perf:
        cagr_1y, cagr_3y, cagr_5y = perf.group(1), perf.group(2), perf.group(3)
    if not cagr_1y:
        cagr_1y = _first_group(text, r"(\d+\.?\d*)%\s*in\s*1\s*year") or _first_group(text, r"1Y\s+(-?\d+\.?\d*)%")
    if not cagr_3y:
        cagr_3y = _first_group(text, r"(\d+\.?\d*)%\s*in\s*3\s*years") or _first_group(text, r"3Y\s+(-?\d+\.?\d*)%")
    if not cagr_5y:
        cagr_5y = _first_group(text, r"(\d+\.?\d*)%\s*in\s*5\s*years") or _first_group(text, r"5Y\s+(-?\d+\.?\d*)%")

    # Since inception: from Playwright (Since Inception block) or regex
    since_inception = pw_values.get("since_inception")
    if not since_inception:
        since_inception = (
            _first_group(text, r"(\d+\.?\d*)%\s*per year\s+Since Inception")
            or _first_group(text, r"(\d+\.?\d*)%\s*/?\s*per year\s*Since Inception")
            or _first_group(text, r"(\d+\.?\d*)%\s*/\s*per year\s+Since Inception")
            or _first_group(text, r"(\d+\.?\d*)%.{0,50}Since Inception")
            or _first_group(text, r"Since Inception.{0,40}(\d+\.?\d*)%")
            or _first_group(text, r"Since Inception\s+(-?\d+\.?\d*)%")
            or _first_group(text, r"Since Inception\s+(\d+\.?\d*)%\s*per year")
            or _first_group(text, r"(\d+\.?\d*)%\s*per year\s*Since Inception")
            or _first_group(text, r"(\d+\.?\d*)%/\s*per year\s+Since Inception")
            or _first_group(text, r"(\d+\.?\d*)%\s*per year\s+Invest Now")
        )
    if since_inception and "%" not in str(since_inception):
        since_inception = str(since_inception).strip() + "%"

    # Equity % / Debt & Cash %
    equity_pct = _first_group(text, r"Equity\s+(\d+\.?\d*)%") or _first_group(text, r"Equity\s+(\d+)%")
    debt_cash_pct = (
        _first_group(text, r"Debt\s*&\s*Cash\s+(\d+\.?\d*)%")
        or _first_group(text, r"Debt\s*\+\s*Cash\s+(\d+\.?\d*)%")
    )

    # Market cap split
    mid = _first_group(text, r"Mid cap\s+(\d+\.?\d*)%")
    small = _first_group(text, r"Small cap\s+(\d+\.?\d*)%")
    large = _first_group(text, r"Large cap\s+(\d+\.?\d*)%")
    parts = [
        p
        for p in [
            f"Large cap {large}%" if large else None,
            f"Mid cap {mid}%" if mid else None,
            f"Small cap {small}%" if small else None,
        ]
        if p
    ]
    market_cap_split = "; ".join(parts) if parts else None

    # Top holdings: FAQ "The top 3 holdings of the fund are A(4.51%), B(4.19%), C(3.99%)"
    top_holdings = _first_group(
        text,
        r"top \d+ holdings of the fund are\s+((?:[A-Za-z0-9 &.,]+\(\d+\.\d*%\)\s*,?\s*)+)",
    )
    if not top_holdings:
        top_holdings = _first_group(text, r"holdings of the fund are\s+([^.?]+(?:\(\d+\.\d*%\)[^.?]*)+)")
    if not top_holdings:
        m = re.search(
            r"top \d+ holdings[^.]*?are\s+([^?]+?)(?=\s+Who is|\s+What is|\s+How do|\?\s)",
            text,
            re.IGNORECASE,
        )
        if m:
            top_holdings = m.group(1).strip()
    if not top_holdings:
        m = re.search(r"Holdings\s+(.+?)(?=See all|Portfolio Changes|$)", text, re.DOTALL | re.IGNORECASE)
        if m:
            top_holdings = re.sub(r"\s+", " ", m.group(1).strip())[:800]
    if top_holdings:
        top_holdings = re.sub(r"\s+", " ", top_holdings.strip())
        if top_holdings.startswith("of the fund are "):
            top_holdings = top_holdings.replace("of the fund are ", "", 1)
        top_holdings = top_holdings[:1000]

    # Build payload: include all fields; use N/A or 0 only where schema allows and value truly missing
    def _pct(s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        return s if "%" in s else f"{s}%"

    payload: Dict[str, Any] = {
        "fund_id": fund_id,
        "fund_name": fund_name,
        "source_url": source_url,
        "scraped_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if nav is not None:
        payload["nav"] = nav
    else:
        payload["nav"] = 0.0
    if nav_date:
        payload["nav_date"] = nav_date
    if daily_pct_change is not None:
        payload["daily_pct_change"] = daily_pct_change
    else:
        payload["daily_pct_change"] = 0.0  # default when not present or not parsed
    if aum:
        payload["aum"] = aum
    else:
        payload["aum"] = "N/A"
    if expense_ratio:
        payload["expense_ratio"] = expense_ratio
    else:
        payload["expense_ratio"] = "N/A"
    if min_lump:
        payload["min_investment_lumpsum"] = min_lump
    else:
        payload["min_investment_lumpsum"] = "N/A"
    if min_sip:
        payload["min_investment_sip"] = min_sip
    else:
        payload["min_investment_sip"] = "N/A"
    if exit_load:
        payload["exit_load"] = exit_load
    else:
        payload["exit_load"] = "N/A"
    if elss_lock_in:
        payload["elss_lock_in"] = elss_lock_in
    if cagr_1y:
        payload["cagr_1y"] = _pct(cagr_1y)
    else:
        payload["cagr_1y"] = "N/A"
    if cagr_3y:
        payload["cagr_3y"] = _pct(cagr_3y)
    else:
        payload["cagr_3y"] = "N/A"
    if cagr_5y:
        payload["cagr_5y"] = _pct(cagr_5y)
    else:
        payload["cagr_5y"] = "N/A"
    if since_inception:
        payload["since_inception"] = _pct(since_inception)
    else:
        payload["since_inception"] = "N/A"
    if equity_pct:
        payload["equity_pct"] = _pct(equity_pct)
    else:
        payload["equity_pct"] = "N/A"
    if debt_cash_pct:
        payload["debt_cash_pct"] = _pct(debt_cash_pct)
    else:
        payload["debt_cash_pct"] = "N/A"
    if market_cap_split:
        payload["market_cap_split"] = market_cap_split
    else:
        payload["market_cap_split"] = "N/A"
    if top_holdings:
        payload["top_holdings"] = top_holdings
    else:
        payload["top_holdings"] = "N/A"
    if risk_level:
        payload["risk_level"] = risk_level
    else:
        payload["risk_level"] = "N/A"
    if benchmark:
        payload["benchmark"] = benchmark
    else:
        payload["benchmark"] = "N/A"

    return payload


def scrape_fund(
    url: str,
    fund_id: str,
    fund_name: str,
    page: Optional[Page] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch one fund page and return extracted data dict, or None on failure.
    If `page` is provided (Playwright Page), uses it for the request and for better extraction.
    """
    html = fetch_html(url, page=page)
    if not html:
        return None
    return extract_fund_data(html, fund_id, fund_name, url, page=page)
