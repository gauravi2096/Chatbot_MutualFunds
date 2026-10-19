"""
Offline tests (no network, no Groq): PII written with spaces or hyphens is blocked while ordinary fund
numbers are not, and loose words such as "value" or "gold" no longer pick a fund on their own.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import phase_2.orchestration as orch
from phase_0.source_registry import PHASE_1_SOURCES
from phase_2.fund_detection import detect_funds_in_query

VALUE = "hdfc-value-fund-direct-plan-growth-option-3623"
GOLD = "hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359"
INFRA = "hdfc-infrastructure-fund-direct-plan-growth-option-3315"
MID = "hdfc-mid-cap-fund-direct-plan-growth-option-3097"

# --- PII ------------------------------------------------------------------------------------------

MUST_BLOCK = {
    "aadhaar": ["123456789012", "1234 5678 9012", "1234-5678-9012", "1234 5678-9012"],
    "pan": ["ABCDE1234F", "ABCDE 1234 F", "ABCDE-1234-F", "abcde 1234 f", "ABCDE-1234F", "ABCDE1234 F", "Abcde - 1234 - K"],
    "mobile": [
        "9876543210", "+91 9876543210", "+919876543210", "91 9876543210", "919876543210", "09876543210", "0 9876543210",
        "98765 43210", "98765-43210", "+91 98765 43210", "91-98765-43210", "0 98765 43210",
        "987 654 3210", "987-654-3210", "+91 987 654 3210",
        "9876 543 210", "9876-543-210", "+91-9876-543-210",
    ],
    "email": ["someone@example.com", "first.last+tag@mail.co.in"],
}
SENTENCE = ["my number is {}, what is the NAV", "{} is mine. What is the expense ratio of HDFC Mid Cap Fund?", "show holdings for {}"]


def test_every_pii_shape_is_blocked_bare_and_inside_a_sentence():
    for shape, samples in MUST_BLOCK.items():
        for sample in samples:
            assert orch.contains_sensitive_info(sample), (shape, sample)
            for template in SENTENCE:
                text = template.format(sample)
                assert orch.contains_sensitive_info(text), (shape, text)


def test_the_stated_aadhaar_sentence_is_blocked():
    assert orch.contains_sensitive_info("my aadhaar is 1234 5678 9012, what is the NAV")
    assert orch.contains_sensitive_info("my aadhaar is 1234-5678-9012, what is the NAV")


MUST_NOT_BLOCK = [
    "SIP of 10,000 a month", "NAV 245.67", "minimum 5000", "AUM of 1,23,456 crore", "expense ratio 0.52",
    "3 year return 18.4", "1 lakh lumpsum", "fund id 3097", "18 Oct 2026", "in 2026", "top 3 holdings",
    "What is the NAV of HDFC Mid Cap Fund?", "I can invest about 5000 a month", "In March 2026 I invested in HDFC Mid Cap Fund",
    "since 2013 a good record", "NAV was 245.67 on 18-Oct-2026", "returns of 12.5 15.2 18.4 over 1 3 5 years",
    "SIP 5000 on 15 Oct 2026", "HDFC Mid Cap Fund 3097 expense ratio", "AUM 40801 Cr and NAV 155.06",
    "Compare 3 year return 18.4 and 5 year return 16.74", "minimum lumpsum 100 and SIP 100", "exit load 1% within 365 days",
    "AUM of 101856 crore", "NAV on 16-10-2026 was 221.06", "the 5 funds with AUM above 5000 crore",
]


def test_normal_fund_questions_are_not_blocked():
    for q in MUST_NOT_BLOCK:
        assert not orch.contains_sensitive_info(q), q


CARD_AND_UPI = [
    "4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111", "4111 1111-1111 1111",     # 16 digits
    "378282246310005", "3782 822463 10005", "3782-822463-10005",                                 # 15 digits (4-6-5)
    "name@okhdfcbank", "9876543210@ybl", "john.doe@oksbi", "abc_12@paytm", "a-b.c@axl",           # UPI ids
]


def test_card_numbers_and_upi_ids_are_blocked_bare_and_inside_a_sentence():
    for sample in CARD_AND_UPI:
        assert orch.contains_sensitive_info(sample), sample
        for template in SENTENCE + ["my card is {}, what is the NAV", "pay me on {} please", "send it to {}."]:
            text = template.format(sample)
            assert orch.contains_sensitive_info(text), text


def test_email_is_still_blocked_and_upi_does_not_weaken_it():
    for email in ("someone@example.com", "first.last+tag@mail.co.in", "a@b.com", "name@bank.example.org"):
        assert orch.contains_sensitive_info(email), email
        assert orch.contains_sensitive_info(f"mail me at {email} today"), email


MUST_NOT_BLOCK_ROUND_4 = [
    "SIP @ 5000", "NAV @ 245.67", "invest @ 10% return", "AUM of 1,23,456 crore", "a 16 year horizon", "fund id 3097",
    "returns @12%", "SIP of 10000 @ 12% for 15 years", "buy @ market price", "1234567890123 crore AUM",
    "NAV 245.67 on 18 Oct 2026", "a 15 year SIP of 5000", "the fund has 79 holdings and AUM 101856 crore",
]


def test_card_and_upi_patterns_do_not_block_normal_questions():
    for q in MUST_NOT_BLOCK_ROUND_4 + MUST_NOT_BLOCK:
        assert not orch.contains_sensitive_info(q), q


def test_ifsc_codes_and_bare_digits_are_left_alone():
    for q in ("IFSC HDFC0001234", "my otp 482913 is not here", "reference 123456", "ticket 12345678"):
        if "otp" in q.lower():
            continue  # the OTP keyword is blocked on purpose
        assert not orch.contains_sensitive_info(q), q


# --- fund aliases -----------------------------------------------------------------------------------

MUST_NOT_DETECT = ["what is value investing", "gold price today", "infrastructure sector outlook",
                   "golden rule of investing", "is gold a good hedge", "valued at 100 crore", "the value of patience",
                   "infrastructure spending in India", "gold rate"]


def test_loose_words_do_not_pick_a_fund():
    for q in MUST_NOT_DETECT:
        assert detect_funds_in_query(q) == [], (q, detect_funds_in_query(q))


def test_whole_word_matching():
    assert detect_funds_in_query("golden") == [] and detect_funds_in_query("valued") == []
    assert detect_funds_in_query("goldfish") == [] and detect_funds_in_query("value fundamentals") == []
    # a generic question about fund-of-funds as a category must not pick the Gold fund
    assert detect_funds_in_query("what is a fund of funds") == []
    assert detect_funds_in_query("a fund of funds overview") == []
    assert detect_funds_in_query("fund of fund") == []


def test_an_optional_plural_s_on_the_last_word_is_allowed():
    cases = [("HDFC Gold ETF Fund of Fund", GOLD), ("gold etf fof", GOLD), ("gold fund", GOLD), ("gold etfs", GOLD), ("NAV of flexi caps", "hdfc-flexi-cap-fund-direct-plan-growth-option-3184"),
             ("mid caps AUM", MID), ("value funds exit load", VALUE), ("small caps", "hdfc-small-cap-fund-direct-growth-option-3580"),
             ("infrastructure funds", INFRA), ("HDFC Mid Cap Funds", MID)]
    for q, fund_id in cases:
        assert detect_funds_in_query(q) == [fund_id], (q, detect_funds_in_query(q))
    # the plural does not make the loose single words match
    for q in ("values", "golds", "infrastructures"):
        assert detect_funds_in_query(q) == [], q


MUST_DETECT = [
    ("value fund NAV", VALUE), ("HDFC Value Fund", VALUE), ("hdfc value", VALUE),
    ("HDFC Gold ETF Fund of Fund", GOLD), ("gold etf fof", GOLD), ("gold fund exit load", GOLD), ("hdfc gold etf", GOLD),
    ("infrastructure fund AUM", INFRA), ("HDFC Infrastructure Fund", INFRA),
]


def test_real_fund_names_and_aliases_still_detect_the_right_fund():
    for q, fund_id in MUST_DETECT:
        assert detect_funds_in_query(q) == [fund_id], (q, detect_funds_in_query(q))


def test_every_registry_name_detects_its_own_fund():
    for fund_id, name in PHASE_1_SOURCES:
        assert detect_funds_in_query(name) == [fund_id], name
        assert detect_funds_in_query(name.lower()) == [fund_id], name
        assert detect_funds_in_query(f"What is the NAV of {name}?") == [fund_id], name


def test_two_fund_comparisons_still_detect_two_funds():
    assert detect_funds_in_query("Compare HDFC Mid Cap Fund and HDFC Value Fund") == [MID, VALUE]
    assert detect_funds_in_query("value fund vs gold fund") == [VALUE, GOLD]
    assert detect_funds_in_query("Compare HDFC Gold ETF Fund of Fund and HDFC Infrastructure Fund AUM") == [GOLD, INFRA]


# --- what the chatbot does with the no-fund queries (flow unchanged) ---------------------------------

def _route(query):
    class NoRetrieval:
        def retrieve(self, *a, **k):
            raise AssertionError(f"retrieval must not run for {query!r}")
    original = orch.chat_completion
    orch.chat_completion = lambda messages, **kw: None  # no Groq: the refusal falls back to its fixed text
    try:
        r = orch.chat(query, retriever=NoRetrieval())
    finally:
        orch.chat_completion = original
    if r.get("is_greeting"):
        return "greeting"
    if r.get("needs_fund_clarification"):
        return "clarify"
    return "advice-refusal" if r.get("rejected") else "answer"


def test_gold_hedge_is_refused_as_advice_not_clarified():
    for q in ("is gold a good hedge", "Is gold a good hedge against inflation?"):
        assert _route(q) == "advice-refusal", q


def test_other_no_fund_queries_ask_which_fund():
    for q in ("what is value investing", "gold price today", "infrastructure sector outlook", "golden rule of investing"):
        assert _route(q) == "clarify", q


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
