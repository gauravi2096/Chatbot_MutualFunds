"""
Phase 2 — Orchestration: RAG retrieval + prompt build + Groq + response shaping.
Ensures every response includes one source link and last data update timestamp.
Handles restricted queries (advisory, sensitive info, comparisons) with polite, professional responses.
"""

import logging
import re
from typing import Optional

from phase_0.source_registry import load_registry
from phase_1.config import REGISTRY_PATH
from phase_1.retriever import Retriever
from phase_2.fund_detection import detect_funds_in_query
from phase_2.groq_client import chat_completion
from phase_2.config import RAG_TOP_K

logger = logging.getLogger(__name__)

# Official source for factual fund data (used in restricted responses)
INDMONEY_BASE = "https://www.indmoney.com/mutual-funds"

# Fixed educational link for advisory-refusal redirects (always this exact URL)
AMFI_FUND_SELECTION_URL = "https://www.mutualfundssahihai.com/en/how-do-i-know-which-fund-right-me"

# Backup for advice phrasings the regex patterns miss; shared by both answer prompts.
_ADVICE_BACKUP_RULE = (
    "- If the user is asking for advice, a recommendation, an opinion, a prediction, or what to do with their money, "
    "do not answer it. Reply in two sentences: say you share facts about these funds, not recommendations, and point "
    f"them to {AMFI_FUND_SELECTION_URL}, then invite a factual question. A plain request to look up or compare facts "
    "(NAV, expense ratio, returns, holdings) is NOT advice. Answer it normally."
)

# Stops the model from reading a missing value as "none" or "free".
_NA_MEANING_RULE = (
    "- N/A means the value is not available in the data. Never say N/A means none, zero, or no charge. "
    "Say it is not available."
)

SYSTEM_PROMPT = """You are a factual assistant for INDmoney mutual fund data. You answer only factual questions about the 10 listed funds (NAV, AUM, expense ratio, returns, holdings, risk, benchmark, etc.) using ONLY the context provided below.

Rules:
- Answer ONLY from the provided context. If the context does not contain the answer, say so and do not guess.
- Do NOT give investment advice, recommendations, or personalized guidance.
- Do NOT compare funds for "best" or "should I invest".
- Keep answers concise and factual. Include the fund name when citing a value.
- Do not include source links or timestamps in your answer text; they will be added separately.
""" + _ADVICE_BACKUP_RULE + "\n" + _NA_MEANING_RULE

COMPARISON_TABLE_SYSTEM_PROMPT = """You are a factual assistant for INDmoney mutual fund data. The user wants a full side-by-side comparison of two funds, using ONLY the context provided below.

Rules:
- Answer ONLY from the provided context. If a value is missing from the context, write "Not available" for that cell rather than guessing.
- Do NOT give investment advice, recommendations, or an opinion on which fund is better.
- Structure your reply as:
  1. A markdown table with one row per field and one column per fund (fund names as column headers), in exactly this field order: NAV, AUM, Expense Ratio, Exit Load, Min Lumpsum, Min SIP, 1Y CAGR, 3Y CAGR, 5Y CAGR, Since Inception, Equity %, Debt+Cash %, Risk Level, Benchmark.
  2. Below the table, a "Top Holdings" section listing each fund's top holdings separately, clearly labeled by fund name (not as a table row).
- Do not include source links or timestamps in your answer text; they will be added separately.
""" + _ADVICE_BACKUP_RULE + "\n" + _NA_MEANING_RULE

ADVISORY_REFUSAL_SYSTEM_PROMPT = f"""You respond when a user asks for investment advice, a fund recommendation, an opinion, which fund to pick or buy, personalized suitability, or a comparison meant to choose one fund over another.

Your role is to share facts about the 10 listed HDFC funds on INDmoney, not recommendations on what to buy.

Response rules (follow every time; vary wording naturally across replies):
- Acknowledge the question is outside your scope in a warm, conversational tone. Avoid compliance-style phrasing such as "I cannot offer investment advice" or "I am not authorized to provide recommendations."
- Redirect the user to this exact educational link (always use this URL verbatim): {AMFI_FUND_SELECTION_URL}
- Close by inviting a factual follow-up about any of the 10 funds (e.g. expense ratio, AUM, exit load, riskometer, NAV, returns, holdings).
- Keep the entire response to 2-3 sentences.
- Do not answer the advisory question, compare funds to recommend one, or include INDmoney source links or data timestamps in your text."""


def build_messages(query: str, context_text: str, source_url: str, last_data_update: str) -> list:
    """Build system + user messages for Groq. Context and format rules are in the user message."""
    user_content = f"""Use the following context to answer the user question. Answer only from this context. Do not give advice or recommendations.

Context:
{context_text}

User question: {query}

Reply with a short, factual answer only."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_comparison_table_messages(query: str, context_text: str) -> list:
    """Build system + user messages for Groq to generate a full comparison table."""
    user_content = f"""Use the following context to build the comparison. Answer only from this context.

Context:
{context_text}

User question: {query}

Follow the exact structure described in your instructions."""

    return [
        {"role": "system", "content": COMPARISON_TABLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# Field keywords that, if named in a comparison query, mean the answer should
# stay narrowed to that one field rather than expanding to the full table
# (e.g. "compare exit load of X and Y"). Deliberately excludes bare "equity"
# and "debt", since those are substrings of fund names themselves (e.g.
# "HDFC Equity Savings Fund", or the older alias "HDFC Dynamic Debt Fund") and would otherwise
# false-positive on a generic "compare these two funds" request.
_FIELD_KEYWORDS = (
    "nav", "aum", "expense", "exit load", "lumpsum", "sip", "cagr",
    "since inception", "inception", "risk", "benchmark", "holding",
    "equity %", "equity allocation", "equity exposure", "equity percentage",
    "debt+cash", "debt %", "debt allocation", "debt exposure", "cash allocation",
)
_FIELD_KEYWORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in _FIELD_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _mentions_specific_field(query: str) -> bool:
    """
    True if the query names a specific data field (e.g. "exit load", "NAV"),
    so the answer should stay narrowed to just that field. False for a
    generic "compare these two funds" request with no field named, which
    should get the full comparison table instead.
    """
    return bool(_FIELD_KEYWORD_PATTERN.search(query))


# Patterns for sensitive personal/financial information (do not store or process).
# Identifiers are also caught when typed with spaces or hyphens between their groups. Each
# pattern is narrow (fixed digit counts, fixed group sizes) so ordinary fund numbers such as
# "NAV 245.67", "SIP of 10,000", "1,23,456 crore", "3097" or "18 Oct 2026" never match.
_PAN_FINAL_LETTER = r"(?:[B-HJ-Z]|[AI](?!\s+\w))"  # a lone "a"/"i" followed by a word is prose ("5000 a month")
_PAN_LETTERS_SPELLED = r"[A-Z](?:[\s-]+[A-Z]){4}"
_PAN_DIGITS_SPELLED = r"[0-9](?:[\s-]+[0-9]){3}"
_PAN_PATTERNS = (
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE),  # ABCDE1234F
    re.compile(r"\b[A-Z]{5}[\s-]+[0-9]{4}(?:[\s-]+" + _PAN_FINAL_LETTER + r"|[A-Z])\b", re.IGNORECASE),  # ABCDE 1234 F, ABCDE-1234F
    re.compile(r"\b[A-Z]{5}[0-9]{4}[\s-]+" + _PAN_FINAL_LETTER + r"\b", re.IGNORECASE),  # ABCDE1234 F
    # One character at a time: "A B C D E 1 2 3 4 F", "A-B-C-D-E 1-2-3-4 F". Same shape (5 letters, 4 digits, 1 letter);
    # at least one of the two groups is spelled out, so the forms above keep their own guards.
    re.compile(r"(?<![A-Za-z0-9])" + _PAN_LETTERS_SPELLED + r"[\s-]*(?:" + _PAN_DIGITS_SPELLED + r"|[0-9]{4})[\s-]*"
               + _PAN_FINAL_LETTER + r"(?![A-Za-z0-9])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}[\s-]*" + _PAN_DIGITS_SPELLED + r"[\s-]*" + _PAN_FINAL_LETTER + r"(?![A-Za-z0-9])", re.IGNORECASE),
)
# Aadhaar: 12 digits in groups of 4, optionally separated by a space or hyphen.
_AADHAAR_PATTERN = re.compile(r"\b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# Indian mobile: 10 digits starting 6-9 (avoids AUM/NAV numbers), optional +91 / 91 / 0 prefix,
# written continuous or split by one or two spaces/hyphens as 5+5, 3+3+4 or 4+3+3.
_MOBILE_START = r"(?<![\w.])(?:(?:\+91|91|0)[\s-]?)?[6-9]"
_PHONE_PATTERNS = (
    re.compile(_MOBILE_START + r"[0-9]{9}(?!\d)"),
    re.compile(_MOBILE_START + r"[0-9]{4}[\s-][0-9]{5}(?!\d)"),
    re.compile(_MOBILE_START + r"[0-9]{2}[\s-][0-9]{3}[\s-][0-9]{4}(?!\d)"),
    re.compile(_MOBILE_START + r"[0-9]{3}[\s-][0-9]{3}[\s-][0-9]{3}(?!\d)"),
)
# Payment card: 15 or 16 digits, continuous or in groups of 4-4-4-4 / 4-6-5 split by a space or hyphen.
_CARD_PATTERNS = (
    re.compile(r"(?<![\d.])[0-9]{15,16}(?!\d)"),
    re.compile(r"(?<![\d.])[0-9]{4}[\s-][0-9]{4}[\s-][0-9]{4}[\s-][0-9]{4}(?!\d)"),
    re.compile(r"(?<![\d.])[0-9]{4}[\s-][0-9]{6}[\s-][0-9]{5}(?!\d)"),
)
# UPI id: a handle of 3+ characters, "@", then a letters-only bank handle with no dot after it
# (name@okhdfcbank, 9876543210@ybl). "name@example.com" is left to the email pattern; "SIP @ 5000" never matches.
_UPI_PATTERN = re.compile(r"(?<![\w.+-])[A-Za-z0-9._-]{3,}@[A-Za-z]{2,}(?![\w-]|\.\w)")


def contains_sensitive_info(query: str) -> bool:
    """Return True if the message appears to contain PAN, Aadhaar, email, or phone numbers."""
    if not query or len(query.strip()) < 4:
        return False
    # PAN (Indian Permanent Account Number)
    if any(p.search(query) for p in _PAN_PATTERNS):
        return True
    # Aadhaar-like 12 digits (possibly spaced or hyphenated)
    if _AADHAAR_PATTERN.search(query):
        return True
    # Email
    if _EMAIL_PATTERN.search(query):
        return True
    # UPI id and payment card number
    if _UPI_PATTERN.search(query) or any(p.search(query) for p in _CARD_PATTERNS):
        return True
    # Indian mobile number
    if any(p.search(query) for p in _PHONE_PATTERNS):
        return True
    # Keywords that often accompany sensitive data
    q = query.lower()
    if any(k in q for k in ("aadhaar", "aadhar", "pan card", "account number", "otp", "one time password")):
        return True
    return False


def build_advisory_refusal_messages(query: str) -> list:
    """Build system + user messages for Groq to generate an advisory-refusal redirect."""
    user_content = f"""User question: {query}

Write a 2-3 sentence redirect response following your rules."""
    return [
        {"role": "system", "content": ADVISORY_REFUSAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generate_advisory_refusal(query: str) -> str:
    """Generate a warm advisory-refusal redirect via Groq, with a structured fallback."""
    reply = chat_completion(build_advisory_refusal_messages(query), temperature=0.5, max_tokens=256)
    if reply:
        return reply
    return (
        "That's outside what I can help with: I share facts about these funds, not recommendations on what to buy. "
        f"For guidance on picking a fund that fits your goals, AMFI has a good primer: {AMFI_FUND_SELECTION_URL}. "
        "Happy to tell you the expense ratio, AUM, exit load, or riskometer for any fund on the list, though."
    )


def is_greeting_or_chitchat(query: str) -> bool:
    """Return True if query is a general greeting or chitchat (and not a financial/fund data query)."""
    if not query or not query.strip():
        return False

    q_clean = query.strip().lower().rstrip("!.?")

    greeting_exact = {
        "hi", "hello", "hey", "hi there", "hello there", "hey there",
        "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "thanks!", "bye", "goodbye",
        "cool", "ok", "okay", "great", "awesome", "help",
        "who are you", "what can you do"
    }
    if q_clean in greeting_exact:
        return True

    greeting_prefixes = ("hi ", "hello ", "hey ", "good morning ", "good afternoon ", "good evening ")
    financial_terms = (
        "nav", "aum", "expense", "ratio", "risk", "return", "cagr",
        "holding", "benchmark", "fund", "hdfc", "invest", "buy", "sell",
        "compare", "performance", "yield"
    )
    if any(q_clean.startswith(prefix) for prefix in greeting_prefixes):
        if not any(term in q_clean for term in financial_terms):
            return True

    return False


# Advice / opinion detection. Case-insensitive regex patterns grouped by the kind
# of question. They describe general constructions ("should I <decision verb>",
# "will <X> go up"), not specific sentences. A construction that can also be a
# plain factual lookup is left out on purpose: the advice rule in SYSTEM_PROMPT
# catches those downstream, and a wrongly refused factual question is the worse
# failure.

# Decision verbs, with an optional ending (invest, investing, sold...). The explicit
# endings keep "holdings", "investment" and "exit load" from matching.
_VERB_ENDING = r"(?:e|s|ing|ed|d)?\b"
_DECISION_STEMS = (
    r"invest|buy|sell|hold|switch|exit(?!\s+load)|redeem|enter|put|park|keep|stay|continue|stop|"
    r"pick|choose|select|go\s+(?:for|with)|wait|book|stick|opt|diversify|allocate|liquidate|"
    r"get\s+(?:in|out)|pull\s+out"
)
_DECISION_VERB = r"(?:" + _DECISION_STEMS + r")" + _VERB_ENDING
# "Is it <verdict> to <verb>" also takes verbs that only make sense as a comparison.
_COMPARATIVE_VERB = r"(?:" + _DECISION_STEMS + r"|do|go|use|take|begin)" + _VERB_ENDING
_VERDICT = (
    r"(?:good|great|bad|wise|smart|sensible|advisable|better|best|ok|okay|fine|safe|right|"
    r"worthwhile|wiser|smarter|safer|preferable|ideal|time)"
)
_RETURN_WORD = r"(?:returns?|growth|gains?|profits?|appreciation|performance|cagr|yield|income|payouts?)"
# Who the user says they are asking for.
_INVESTOR = (
    r"(?:me|us|my|someone|anyone|people|those|beginners?|investors?|seniors?|retirees?|first[- ]time|"
    r"conservative|aggressive|moderate|young|old|elderly|risk[- ]averse|retired|"
    r"an?\s+(?:beginner|senior|retiree|investor|person|conservative|aggressive|moderate|young|new|"
    r"first[- ]time|risk[- ]averse|long|short|\d+))"
)


def _compile(*patterns: str) -> tuple:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


# buy / sell / hold / switch / exit decisions
_DECISION_PATTERNS = _compile(
    r"\b(?:should|shall|ought\s+to)\s+(?:i|we)\b(?:\W+\w+){0,3}?\W+" + _DECISION_VERB,
    r"\b(?:is|was|would|will)\s+it\s+(?:a\s+|the\s+)?" + _VERDICT
    + r"(?:\s+(?:idea|time|move|call|moment))?(?:\s+\w+){0,2}?\s+to\s+" + _COMPARATIVE_VERB,
    r"\bwhat\s+(?:should|shall)\s+(?:i|we)\s+(?:do|buy|pick|choose|select|invest|go\s+for)\b",
    r"\bwhat\s+to\s+do\s+with\s+(?:my|the|these|this|our)\b",
    r"\btell\s+me\s+what\s+to\s+(?:do|buy|pick|choose|invest|sell|hold)\b",
    r"\bwhere\s+(?:\w+\s+){0,3}?should\s+(?:i|we)\b",
    r"\bwhere\s+(?:can|could|do|to|would|might|shall)\s+(?:(?:i|we)\s+)?(?:[\w']+\s+){0,2}?(?:put|park|invest|deploy|keep|stash|place|"
    r"use|save|lock)\s+(?:(?:my|our|the|this|some|these|that|more|all)\s+)?(?:[\w']+\s+){0,2}?"
    r"(?:money|savings|cash|corpus|bonus|amount|capital|salary|lakhs?|crores?)\b",
    r"\bhow\s+(?:much|many)\b.{0,60}?\b(?:should|shall)\s+(?:i|we)\b",
    r"\b(?:smarter|wiser|better|safer|advisable|sensible|preferable)\s+to\s+" + _COMPARATIVE_VERB,
)

# predictions about future performance
_PREDICTION_FALL = r"fall(?!\s+(?:under|into|within|in\s+the|on|short))"
_PREDICTION_VERB = (
    r"(?:go(?:es)?\s+up|go(?:es)?\s+down|rise|rally|" + _PREDICTION_FALL + r"|drop|crash|increase|decrease|"
    r"grow|appreciate|beat|outperform|outpace|underperform|double|triple|recover|bounce|perform|"
    r"do\s+(?:well|better)|give\s+(?:\w+\s+){0,4}?(?:returns?|profits?|gains?))\b"
)
_PREDICTION_PATTERNS = _compile(
    r"\bwill\b(?:\W+\w+){0,8}?\W+" + _PREDICTION_VERB,
    r"\b(?:likely|expected|going|bound|set|poised|supposed)\s+to\s+" + _PREDICTION_VERB,
    r"\b(?:can|could|would|able\s+to)\b(?:\W+\w+){0,8}?\W+(?:beat|outperform|outpace)\b",
    r"\b(?:expect\w*|anticipat\w+|project\w*)\b(?:\W+\w+){0,6}?\W+" + _RETURN_WORD + r"\b",
    r"\b" + _RETURN_WORD + r"\b(?:\W+\w+){0,6}?\W+(?:can|could|should|will|would|do)\s+(?:i|we|one)\s+"
    r"(?:\w+\s+)?(?:expect|anticipate|get|earn|make)\b",
    r"\b(?:future|forecast\w*|projected|projection)\s+(?:returns?|growth|performance|nav|value|price)\b",
    r"\bgrowth\s+potential\b|\bupside\b",
    # "which fund will give/earn/deliver ... returns" (a forecast), "which fund will grow/beat/outperform", "which fund gives me ..."
    r"\bwhich\s+(?:[\w']+\s+){0,3}?(?:will|would|might|going\s+to)\s+(?:[\w']+\s+){0,2}?(?:give|yield|earn|deliver|generate|fetch|pay)\b"
    r"(?:\W+\w+){0,6}?\W+(?:returns?|profits?|gains?|income|money|growth|yield|payouts?)\b",
    r"\bwhich\s+(?:[\w']+\s+){0,3}?(?:will|would|might|going\s+to)\s+(?:[\w']+\s+){0,2}?(?:grow|rise|double|beat|outperform|outpace|"
    r"do\s+(?:well|better|best)|perform)\b",
    r"\bwhich\s+(?:[\w']+\s+){0,3}?(?:gives?|yields?|earns?|delivers?|pays?|offers?|generates?|fetch(?:es)?|makes?)\s+(?:me|us)\b",
    r"\bwhat\s+(?:will|would|can|could)\s+(?:[\w']+\s+){0,3}?(?:give|earn|yield|deliver|fetch|make)\s+(?:me|us)\b",
)

# the user describes their own situation and asks what to do
_PERSONAL_CONTEXT = _compile(
    r"\b(?:i'?m|i\s+am|i've|i\s+have|i\s+got|i\s+just\s+got|i\s+want|i\s+wanna|i\s+plan|i\s+need|"
    r"i\s+would\s+like|i'd\s+like|we\s+want|we\s+have)\b",
    r"\bmy\s+(?:risk|goals?|age|salary|income|budget|savings?|retire\w*|horizon|family|kids?|"
    r"child\w*|investment|portfolio|money|corpus|bonus)\b",
    r"\b(?:retiring|retirement|bonus)\b",
)
_PERSONAL_SEEKING = _compile(
    r"\b(?:which|what|where)\b(?:\W+\w+){0,6}?\W+(?:should|would|fits?|suits?|ideal|"
    r"(?:highest|best|top)\s+returns?)\b",
)

# opinion, valuation, rating
_OPINION_PATTERNS = _compile(
    r"\b(?:your|ur)\s+(?:view|views|opinion|opinions|take|thoughts?|verdict|assessment|"
    r"recommendations?|advice|suggestions?|pick|picks|choice|call|favou?rite|rating)\b",
    r"\bwhat\s+do\s+you\s+(?:think|feel|reckon|say)\b",
    r"\b(?:do|did|would|will|can|could)\s+you\s+(?:\w+\s+)?(?:like|love|prefer|favou?r|trust|think|rate|"
    r"believe|feel|reckon|endorse|vouch|personally|go\s+for|bet\s+on|put\s+your)\b",
    r"\bhelp\s+me\s+(?:to\s+)?(?:choose|pick|decide|select|invest|find\s+(?:the\s+)?(?:best|right|good|"
    r"ideal|suitable)|plan\s+my)\b",
    r"(?:^|[.!?]\s+|\bplease\s+|\b(?:can|could)\s+you\s+)rate\s+(?!of\s|and\s)",
    r"\bany\s+good\b|\b(?:really|actually|truly)\s+good\b|\bgood\s+or\s+bad\b|\bgood\s+enough\b",
    r"\b(?:is|are)\b(?:\W+\w+){0,10}?\W+(?:a\s+|an\s+|the\s+)?(?:good|great|smart|wise|sensible|solid|"
    r"decent|safe|bad|poor|worthwhile|reliable|trustworthy)\s+(?:investment|buy|pick|choice|option|bet|"
    r"idea|move|fund|scheme|place|call|performer|one|fit|match|opportunity|candidate|hedge)s?\b",
    r"(?<!net )\bworth\s+(?:it|the\s+(?:money|risk|hype|price|investment|cost|wait)|investing|buying|"
    r"holding|keeping|considering|picking|choosing|having|a\s+(?:buy|shot|look|try))\b",
    r"\b(?:over|under)[\s-]?(?:valued|priced|rated|hyped)\b|\bfairly\s+(?:valued|priced)\b|\bbubble\b",
    r"\b(?:can|could|should|would|do|may)\s+(?:i|we)\s+(?:\w+\s+){0,2}?trust\b",
    r"\btrust\w*\b(?:\W+\w+){0,6}?\W+(?:savings|money|corpus|retirement)\b",
    r"\bany\s+(?:advice|suggestions?|recommendations?|tips|ideas?|pointers|guidance)\b",
    r"\b(?:give|need|want|seeking|looking\s+for|share)\s+(?:me\s+)?(?:some\s+|your\s+|any\s+)?"
    r"(?:advice|guidance|suggestions?|recommendations?|tips)\b",
    r"\b(?:advice|guidance)\s+(?:on|about|for|regarding)\s+(?:where|which|what|how|whether|when|"
    r"investing|choosing|buying|selling)\b",
    r"\b(?:deserves?|worth|merits?)\s+(?:of\s+)?(?:my|our)\s+(?:[\w']+\s+){0,2}?(?:money|savings|investment|rupees|capital|"
    r"cash|funds?|corpus|trust|attention|time)\b",
)

# timing
_TIMING_PATTERNS = _compile(
    r"\b(?:good|great|bad|right|wrong|best|perfect|ideal|proper|safe|apt)\s+time\s+(?:to|for)\b",
    r"\btime\s+to\s+" + _DECISION_VERB,
    r"\bwait\w*\s+(?:for|until|till)\s+(?:a\s+|an\s+|the\s+|some\s+)?(?:\w+\s+)?"
    r"(?:dips?|corrections?|falls?|crash\w*|drops?|lows?|bottom|pullbacks?|rally)\b",
    r"\b(?:buy|invest|enter|average)\s+(?:on|at|during|in)\s+(?:the\s+|a\s+)?(?:dips?|corrections?|lows?|crash)\b",
    r"\bbuy\s+the\s+dip\b",
)

# suitability and safety for the asker
_SUITABILITY_PATTERNS = _compile(
    r"\bsuit(?:s|ed)?\s+(?:a|an|my|me|us|someone|the\s+\w+\s+investor|investors?|people|those|anyone|beginners?)\b",
    r"\b(?:good|right|best|suitable|ideal|appropriate|fine|ok|okay|safe|better|perfect|apt|fit)\s+(?:for|to)\s+"
    + _INVESTOR + r"\b",
    r"\bfits?\s+(?:me|my|our|your)\b|\bfit\s+for\s+(?:me|my)\b",
    r"\bsafe\s+(?:to\s+(?:put|invest|park|keep|hold|buy|deposit)|place|bet|option|investment|for\s+"
    + _INVESTOR + r")\b",
    # "the safest/best/right fund to put my parents' money in"
    r"\b(?:safest|safer|best|better|right|ideal|suitable|perfect|top|most\s+(?:suitable|stable|secure|reliable))\s+(?:[\w']+\s+){0,3}?"
    r"(?:funds?|schemes?|options?|investments?|places?|choices?|picks?|ones?|avenues?)\s+(?:[\w']+\s+){0,2}?(?:to|for)\s+"
    r"(?:[\w']+\s+){0,2}?(?:put|park|invest|deposit|keep|save|allocate|place|stash|use|lock|grow|add)\b",
    # "which fund is safest/best for my parents' money / my family"
    r"\b(?:which|what)\s+(?:[\w']+\s+){0,3}?(?:is|are|would\s+be)\s+(?:the\s+)?(?:safest|safer|best|most\s+(?:suitable|stable|secure)|ideal|"
    r"right)\s+(?:[\w']+\s+){0,3}?for\s+(?:my|our)\s+(?:[\w']+\s+){0,2}?(?:money|savings|parents?|family|mother|father|wife|husband|"
    r"kids?|children|retirement|corpus|funds?)\b",
)

# asking Fin to recommend, or to choose between funds
_RECOMMENDATION_PATTERNS = _compile(
    r"\b(?:can|could|would|will|do|did|may)\s+you\s+(?:please\s+)?(?:\w+\s+)?(?:recommend|suggest|advise)\b",
    r"\bwhat\s+(?:do|would|will)\s+you\s+(?:\w+\s+)?(?:recommend|suggest|advise|pick|choose|prefer)\b",
    r"(?:^|[.!?]\s*)(?:please\s+)?(?:recommend|suggest|advise)\b",
    r"\b(?:recommend|suggest)\s+(?:me\s+|us\s+)?(?:a|an|any|some|the\s+best|the\s+right|one|something|"
    r"which|where|what|funds?|schemes?)\b",
    r"\b(?:fund|investment|scheme)\s+(?:recommendations?|suggestions?|advice)\b",
    r"\bwhich\s+(?:\w+\s+){0,4}?(?:should|would|shall)\s+(?:i|we|you)\b",
    r"\bwhich\s+(?:\w+\s+){0,4}?(?:do|will)\s+(?:i|we|you)\s+(?:\w+\s+)?(?:pick|choose|prefer|like|go|put|"
    r"buy|invest|select|recommend|suggest|favou?r|think|rate|back|trust|opt|take)\w*",
    r"\bwhich\s+(?:one\s+|fund\s+|scheme\s+|option\s+)?(?:\w+\s+){0,3}?(?:is|are|would\s+be|will\s+be)\s+"
    r"(?:the\s+|a\s+)?(?:better|best|smarter|wiser|safer|superior|ideal)\b",
    r"\b(?:better|best|smarter|wiser|safer|stronger|superior)\s+(?:pick|choice|option|bet|buy|investment|"
    r"fund|scheme|idea|call|performer|one|candidate|fit)s?\b",
    r"\b(?:best|top)[\s-]performing\b",
    r"\b(?:calculate|compute)\s+(?:my\s+|the\s+)?returns\b",
    r"\bwhich\s+(?:[\w']+\s+){0,3}?(?:beats?|outperforms?|outpaces?|tops?|wins|is\s+(?:the\s+)?(?:winner|leader))\s+(?:all\s+)?"
    r"(?:the\s+)?(?:others?|rest|them|all|everyone|everything|these|those|each\s+other)\b",
    r"\bwhich\s+(?:[\w']+\s+){0,3}?(?:is|are)\s+(?:the\s+)?(?:best|top|number\s+one|winner)\s+(?:of|among|amongst|out\s+of)\s+"
    r"(?:all|them|these|those|the\s+\w+)\b",
)

# splitting money across funds
_ALLOCATION_PATTERNS = _compile(
    r"\bhow\s+(?:should|shall|can|could|would|do|to)\s+(?:(?:i|we)\s+)?(?:[\w']+\s+){0,2}?(?:split|divide|allocate|distribute|spread|"
    r"diversify|apportion)\b[^?.!]{0,80}?\b(?:money|savings?|salary|bonus|investment|amount|corpus|funds?|lakhs?|crores?|rs\.?|rupees?|"
    r"\u20b9|\d[\d,]*)",
    r"\bwhat\s+(?:[\w']+\s+){0,2}?(?:allocation|split|ratio|mix|proportion|weightage|percentage)\s+(?:should|shall|do|would)\s+(?:i|we)\b",
    r"\b(?:suggest|advise|tell\s+me|help\s+me|recommend)\b[^?.!]{0,40}\b(?:split|allocation|allocate|distribute|divide|spread)\b"
    r"[^?.!]{0,40}\b(?:money|savings?|investment|amount|funds?)\b",
)

# Roman-Hindi (Hinglish) advice: "konsa fund lena chahiye", "invest karun ya nahi", "paisa lagana sahi rahega", "SIP shuru karni chahiye".
# Devanagari script is not covered.
_HG_WHICH = r"(?:kon\s?sa|kaun\s?sa|kon\s?si|kaun\s?si|konse|kaunse|konsi|kaunsi)"
_HG_VERDICT = r"(?:chahiye|chahie|sahi|theek|thik|behtar|better|best|accha|achha|acha|rahega|rahegi|hoga|hogi|ya\s+nahi|ya\s+nahin|ya\s+nhi)"
_HINGLISH_PATTERNS = _compile(
    r"\b" + _HG_WHICH + r"\b(?:\W+\w+){0,5}?\W+(?:behtar|best|better|accha|achha|acha|sahi|safe|lena|lun|loon|chahiye|chahie|kharidun|"
    r"khareedun|lagaun|lagau|lagana)\b",
    r"\b(?:kis|" + _HG_WHICH + r")\s+(?:fund|scheme|option|plan|company|stock)s?\s+(?:mein|me|main|men)\s+(?:\w+\s+){0,2}?"
    r"(?:paisa|paise|invest|nivesh|lagau\w*|lagana|lagayein|daal\w*|dal\w*)",
    r"\binvest\s+(?:karu|karun|karoon|krun|kru|karein|karna|karni)\b(?:\W+\w+){0,4}?\W+" + _HG_VERDICT + r"\b",
    r"\b(?:paisa|paise|rupaye|rupay|savings?)\s+(?:\w+\s+){0,2}?(?:lagana|lagaun|lagau|lagaoon|lagayein|lagayen|lagaye|dalna|daalna|"
    r"daalun|dalun)\b(?:\W+\w+){0,4}?\W+" + _HG_VERDICT + r"\b",
    r"\b(?:sip|investment|nivesh)\s+(?:\w+\s+){0,2}?(?:shuru|start|chalu|suru)\s+(?:karni|karna|karun|karu|karoon|karein|kar\s+du|krun|kru)"
    r"\b(?:\W+\w+){0,3}?\W+" + _HG_VERDICT + r"\b",
    r"\b(?:fund|scheme|sip|stock)s?\s+(?:\w+\s+){0,2}?(?:lena|lun|loon|lu|khareedna|kharidna|kharidun|khareedun)\s+" + _HG_VERDICT + r"\b",
    r"\b(?:best|achha|accha|acha|behtar|sabse\s+(?:achha|accha|acha|behtar|safe|best))\s+(?:\w+\s+){0,2}?(?:fund|scheme|option|sip)\b"
    r"(?:\W+\w+){0,3}?\W+(?:batao|bataiye|bataye|btao|suggest|chahiye|dikhao)\b",
    # "sahi rahega / behtar hai" about putting money in: needs an investing word as well
    r"^(?=.*\b(?:invest|lagana|lagaun|lagao|lagau|khareed\w*|kharid\w*|bechna|nivesh|paisa|paise|sip)\b)"
    r"(?=.*\b(?:sahi|theek|behtar|achha|accha|acha)\s+(?:rahega|rahegi|hoga|hogi|hai|rahenge)\b)",
)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.replace("’", "'")).strip()


def _matches_any(patterns: tuple, text: str) -> bool:
    return any(p.search(text) for p in patterns)


def is_likely_advisory(query: str) -> bool:
    """True if the query asks for advice, an opinion, a prediction or a decision about the user's money."""
    q = _normalize_query(query)
    if _matches_any(_PERSONAL_CONTEXT, q) and _matches_any(_PERSONAL_SEEKING, q):
        return True
    return any(
        _matches_any(group, q)
        for group in (
            _DECISION_PATTERNS,
            _PREDICTION_PATTERNS,
            _OPINION_PATTERNS,
            _TIMING_PATTERNS,
            _SUITABILITY_PATTERNS,
            _ALLOCATION_PATTERNS,
            _HINGLISH_PATTERNS,
        )
    )


def is_comparison_or_recommendation(query: str) -> bool:
    """True if the query asks Fin to recommend a fund or to pick the better of several.

    A plain request to compare facts ("compare the returns of X and Y") is not matched.
    """
    return _matches_any(_RECOMMENDATION_PATTERNS, _normalize_query(query))


def _get_last_data_update() -> str:
    """Load last data update timestamp from the source registry without retrieval."""
    try:
        registry = load_registry(REGISTRY_PATH)
        return registry.last_data_update or ""
    except Exception:
        return ""


def _restricted_response(
    message: str,
    source_url: str,
    last_data_update: str,
    rejected: bool = True,
) -> dict:
    """Return a standard response dict for restricted queries."""
    url = source_url.strip() or INDMONEY_BASE
    return {
        "message": message,
        "source_url": url,
        "last_data_update": last_data_update,
        "rejected": rejected,
    }


def _build_sources(chunks: list, fund_id_clean: Optional[str], detected_fund_ids: list) -> list:
    """
    Build the list of {fund_name, source_url} sources for a response, one per
    fund actually being answered about:
      - Single fund (fund_id_clean set): exactly 1 source for that fund.
      - Comparison (fund_id_clean is None, 2+ funds named): one source per
        named fund, limited to funds that were actually retrieved - not
        however many chunks the unscoped top-k search happened to surface,
        which isn't limited to just the named funds and can include others.
    """
    if fund_id_clean is not None:
        matches = [c for c in chunks if c.get("fund_id") == fund_id_clean]
        selected = matches[:1]
    elif len(detected_fund_ids) >= 2:
        chunks_by_fund = {c["fund_id"]: c for c in chunks if c.get("fund_id")}
        selected = [chunks_by_fund[fid] for fid in detected_fund_ids if fid in chunks_by_fund]
    else:
        selected = chunks[:1]

    return [
        {"fund_name": c.get("fund_name", ""), "source_url": c.get("source_url", "")}
        for c in selected
        if c.get("source_url")
    ]


def chat(
    query: str,
    retriever: Optional[Retriever] = None,
    top_k: Optional[int] = None,
    fund_id: Optional[str] = None,
) -> dict:
    """
    Run RAG + Groq pipeline with Intent Classification running FIRST:
    1. Greeting / Chitchat -> friendly conversational reply, no retrieval.
    2. Sensitive info -> refusal response.
    3. Advisory / Opinion -> AMFI redirect refusal response.
    4. Factual query (0 funds named in "All funds" mode) -> request fund clarification.
    5. Factual query (1 or 2+ funds named) -> RAG retrieval + factual answer.
    """
    retriever = retriever or Retriever()
    k = top_k or RAG_TOP_K
    fund_id_clean = (fund_id or "").strip() or None

    # Intent 1: Greeting / Chitchat
    if is_greeting_or_chitchat(query):
        return {
            "message": "Hi! Ask me about any of the 10 HDFC funds — expense ratio, NAV, risk level, and more.",
            "source_url": "",
            "last_data_update": _get_last_data_update(),
            "rejected": False,
            "is_greeting": True,
            "needs_fund_clarification": False,
        }

    # Intent 2A: Sensitive personal/financial information
    if contains_sensitive_info(query):
        return _restricted_response(
            "Thank you for reaching out. This chatbot cannot accept, store, or process any personal or financial information such as PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers. Please do not share such details here. For factual information about HDFC mutual funds (e.g. NAV, AUM, expense ratio, or returns), feel free to ask a specific question—I’ll be glad to help with that.",
            "",
            _get_last_data_update(),
            rejected=True,
        )

    # Intent 2B: Advisory / Opinion-seeking query
    if is_likely_advisory(query) or is_comparison_or_recommendation(query):
        return _restricted_response(
            generate_advisory_refusal(query),
            "",
            _get_last_data_update(),
            rejected=True,
        )

    # Intent 3 / 4 / 5: Factual queries in "All funds" mode
    detected_fund_ids: list = []
    if fund_id_clean is None:
        detected_fund_ids = detect_funds_in_query(query)
        if len(detected_fund_ids) == 0:
            return {
                "message": "Which fund would you like to know about?",
                "source_url": "",
                "last_data_update": _get_last_data_update(),
                "rejected": False,
                "needs_fund_clarification": True,
            }
        if len(detected_fund_ids) == 1:
            fund_id_clean = detected_fund_ids[0]

    retrieved = retriever.retrieve(query=query, top_k=k, fund_id=fund_id_clean)
    source_url = retrieved.get("source_url", "")
    last_data_update = retrieved.get("last_data_update", "")
    chunks = retrieved.get("chunks", [])

    context_text = "\n\n---\n\n".join(c.get("text", "") for c in chunks if c.get("text"))
    if not context_text.strip():
        return {
            "message": "I don't have enough data to answer that. Please ask a factual question about one of the 10 INDmoney funds (e.g. NAV, expense ratio, returns).",
            "source_url": source_url or "",
            "last_data_update": last_data_update,
            "rejected": False,
        }

    is_generic_comparison = (
        fund_id_clean is None
        and len(detected_fund_ids) >= 2
        and not _mentions_specific_field(query)
    )
    if is_generic_comparison:
        messages = build_comparison_table_messages(query, context_text)
    else:
        messages = build_messages(query, context_text, source_url, last_data_update)
    reply = chat_completion(messages)
    if not reply:
        return {
            "message": "I couldn't generate a response right now. Please try again.",
            "source_url": source_url or "",
            "last_data_update": last_data_update,
            "rejected": False,
        }

    return {
        "message": reply,
        "source_url": source_url or "",
        "sources": _build_sources(chunks, fund_id_clean, detected_fund_ids),
        "last_data_update": last_data_update,
        "rejected": False,
    }
