"""
Detect which of the 10 Phase 1 funds are mentioned in a user query.

Used in "All funds" mode to block ambiguous retrieval when no fund is named.
"""

import re

from phase_0.source_registry import PHASE_1_SOURCES

# (fund_id slug, aliases for partial matching). Current source names come first; the earlier
# names stay as aliases so queries that still use them keep working.
_FUND_ALIASES: list[tuple[str, list[str]]] = [
    (
        "hdfc-infrastructure-fund-direct-plan-growth-option-3315",
        ["hdfc infrastructure fund", "infrastructure fund"],
    ),
    (
        "hdfc-mid-cap-fund-direct-plan-growth-option-3097",
        ["hdfc mid cap fund", "mid cap fund", "mid cap", "midcap"],
    ),
    (
        "hdfc-small-cap-fund-direct-growth-option-3580",
        ["hdfc small cap fund", "small cap fund", "small cap", "smallcap"],
    ),
    (
        "hdfc-flexi-cap-fund-direct-plan-growth-option-3184",
        ["hdfc flexi cap fund", "flexi cap fund", "flexi cap", "flexicap"],
    ),
    (
        "hdfc-value-fund-direct-plan-growth-option-3623",
        ["hdfc value fund", "hdfc value", "value fund"],
    ),
    (
        "hdfc-dynamic-debt-plan-direct-plan-growth-option-513",
        ["hdfc dynamic term fund", "dynamic term fund", "dynamic term",
         "hdfc dynamic debt fund", "dynamic debt fund", "dynamic debt"],
    ),
    (
        "hdfc-low-duration-direct-plan-growth-option-1481",
        ["hdfc ultra short to short term fund", "ultra short to short term fund", "ultra short to short term",
         "ultra short", "hdfc low duration", "low duration"],
    ),
    (
        "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359",
        ["hdfc gold etf fund of fund", "gold etf fund of fund",
         "hdfc gold etf fof", "gold etf fof", "gold etf", "gold fof", "hdfc gold", "gold fund"],
    ),
    (
        "hdfc-hybrid-equity-fund-direct-growth-option-4103",
        ["hdfc aggressive hybrid fund", "aggressive hybrid fund", "aggressive hybrid",
         "hdfc hybrid equity fund", "hybrid equity fund", "hybrid equity"],
    ),
    (
        "hdfc-equity-savings-fund-direct-plan-growth-option-4569",
        ["hdfc equity savings fund", "equity savings fund", "equity savings"],
    ),
]

# Full display names from registry (exact match)
_NAME_TO_ID = {name.lower(): slug for slug, name in PHASE_1_SOURCES}


def _find_whole_word(text: str, phrase: str) -> int:
    """
    Index of `phrase` in `text` as whole words ("gold" never matches "golden"), or -1.
    The last word may carry a plural "s" ("gold etfs", "flexi caps", "value funds").
    """
    m = re.search(r"(?<!\w)" + re.escape(phrase) + r"s?(?!\w)", text)
    return m.start() if m else -1


def detect_funds_in_query(query: str) -> list[str]:
    """
    Return fund_id slugs mentioned in query (exact name or clear partial match).
    Order follows first appearance in the query text. Duplicates removed.
    """
    if not query or not query.strip():
        return []

    q_lower = query.lower()
    found: list[tuple[int, str]] = []

    for slug, name in PHASE_1_SOURCES:
        pos = _find_whole_word(q_lower, name.lower())
        if pos >= 0:
            found.append((pos, slug))

    for slug, aliases in _FUND_ALIASES:
        if any(s == slug for _, s in found):
            continue
        best_pos = -1
        for alias in aliases:
            pos = _find_whole_word(q_lower, alias)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_pos = pos
        if best_pos >= 0:
            found.append((best_pos, slug))

    found.sort(key=lambda x: x[0])
    seen: set[str] = set()
    ordered: list[str] = []
    for _, slug in found:
        if slug not in seen:
            seen.add(slug)
            ordered.append(slug)
    return ordered
