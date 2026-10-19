"""
Offline tests (no network, no model) for the broadened PAN and advice patterns.

Each new concept has paraphrases of our own that must be refused, near-miss factual sentences that must not be, and the
real chat() is called with the model stubbed to fail, to prove advice and PII are refused BEFORE any answer-model call.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import phase_2.orchestration as orch

PII_MESSAGE = "cannot accept, store, or process"
AMFI = "mutualfundssahihai.com"


def advice(q):
    return orch.is_likely_advisory(q) or orch.is_comparison_or_recommendation(q)


# --- concepts that must be refused, and near-misses that must not -------------------------------------------

CONCEPTS = {
    "which fund will give/earn/deliver returns (a prediction)": (
        ["Which scheme will deliver the best returns for me next year?", "Which HDFC fund is going to give the highest returns?",
         "Which fund gives me the most profit?", "Which fund would earn me the best returns over 5 years?",
         "Which fund will make me the most money?"],
        ["What are the 1 year returns of HDFC Flexi Cap Fund?", "Which HDFC fund gave the best returns last year?",
         "What is the 3 year CAGR of HDFC Value Fund?", "Which HDFC fund has the highest 5 year return?",
         "Which HDFC fund has the highest AUM?", "Which HDFC fund will give the lowest exit load?"],
    ),
    "the safest/best/right fund to put money in": (
        ["Which is the most suitable scheme to park my emergency money?", "Tell me the best fund to invest my savings in.",
         "What is the ideal fund to put my family's money in?", "Which fund is safest for my retirement savings?",
         "What's the best HDFC fund to keep my mother's money in?"],
        ["What is the risk level of HDFC Small Cap Fund?", "Which HDFC fund has the lowest risk level?",
         "What is the risk label of HDFC Gold ETF Fund of Fund?", "What is the safest risk label of HDFC Gold ETF Fund of Fund?",
         "Is the riskometer for HDFC Value Fund Very High?"],
    ),
    "how to split / allocate money across funds": (
        ["How do I divide 2 lakh between mid cap and small cap funds?", "How should I allocate my monthly 20,000 among these schemes?",
         "What allocation should I keep between equity and debt funds?", "Suggest a split of my savings across the funds.",
         "How can I distribute my bonus over three funds?"],
        ["How is the AUM split across holdings of HDFC Flexi Cap Fund?", "What is the asset allocation of HDFC Aggressive Hybrid Fund?",
         "How does HDFC Equity Savings Fund allocate its assets?", "What is the market cap split of HDFC Mid Cap Fund?",
         "What percentage of HDFC Value Fund is in equity?"],
    ),
    "which fund beats the others / deserves my money": (
        ["Which scheme outperforms all the others and is worth my savings?", "Which one tops the rest?",
         "Does HDFC Value Fund deserve my money?", "Which is the best of all these funds?", "Which fund is the winner among them?"],
        ["Which HDFC fund outperformed its benchmark?", "Did HDFC Value Fund beat its benchmark last year?",
         "Which HDFC fund has the best 5 year return?", "How does HDFC Mid Cap Fund compare with its benchmark?",
         "Compare the NAV of HDFC Mid Cap Fund and HDFC Small Cap Fund."],
    ),
    "where should I put / park / invest my money": (
        ["Where can I park my savings safely?", "Where to put my bonus money?", "Where could I invest 5 lakh rupees?",
         "Where should I put my money?", "Where do I keep my emergency cash?"],
        ["Where can I invest in HDFC funds?", "Where can I find the factsheet of HDFC Mid Cap Fund?",
         "Where does HDFC Value Fund get its NAV data from?", "Where is the source of the HDFC Small Cap Fund data?",
         "Where can I see the top holdings of HDFC Flexi Cap Fund?"],
    ),
    "Hinglish (Roman Hindi) advice": (
        ["Kaunsa scheme sabse achha rahega mere liye?", "Kis fund mein paisa lagaun?", "Mujhe ek achha fund batao",
         "Kya SIP start karna chahiye?", "Paisa lagana sahi rahega kya?", "Konsa fund best hai?", "Invest karun ya nahi?",
         "Mujhe kaun sa fund lena chahiye?", "Kya HDFC Value Fund mein invest karna sahi hoga?"],
        ["HDFC Mid Cap ka NAV kya hai?", "HDFC Value Fund ka expense ratio batao", "HDFC Small Cap Fund ki AUM kitni hai?",
         "HDFC Flexi Cap ka exit load kitna hai?", "HDFC Gold ETF Fund of Fund ka benchmark kya hai?",
         "HDFC Infrastructure Fund ke top holdings batao", "HDFC Mid Cap ka risk level kya hai?"],
    ),
}


def test_each_new_concept_refuses_paraphrases():
    for concept, (should_refuse, _) in CONCEPTS.items():
        assert len(should_refuse) >= 3, concept
        for q in should_refuse:
            assert advice(q), f"[{concept}] not refused: {q!r}"


def test_near_miss_factual_sentences_are_not_refused():
    for concept, (_, near_misses) in CONCEPTS.items():
        assert len(near_misses) >= 3, concept
        for q in near_misses:
            assert not advice(q), f"[{concept}] wrongly refused: {q!r}"
            assert not orch.contains_sensitive_info(q), f"[{concept}] wrongly blocked: {q!r}"


# --- the ordinary factual questions of the golden set must stay answerable ---------------------------------

GOLDEN_FACTUAL = [
    "What is the expense ratio of HDFC Mid Cap Fund?", "What is the AUM of HDFC Flexi Cap Fund?", "What is the latest NAV of HDFC Small Cap Fund?",
    "What is the exit load for HDFC Value Fund?", "What is the minimum SIP amount for HDFC Hybrid Equity Fund?",
    "What is the minimum lumpsum investment for HDFC Equity Savings Fund?", "What is the risk level of HDFC Gold ETF FoF?",
    "What is the benchmark of HDFC Mid Cap Fund?", "What is the 1 year return of HDFC Flexi Cap Fund?", "What is the 3 year CAGR of HDFC Small Cap Fund?",
    "What is the 5 year return of HDFC Value Fund?", "What are the returns since inception for HDFC Mid Cap Fund?",
    "What is the equity allocation of HDFC Hybrid Equity Fund?", "What are the top holdings of HDFC Flexi Cap Fund?",
    "Does HDFC Mid Cap Fund have a lock-in period?", "What is the expense ratio of HDFC Dynamic Debt Fund?", "What is the AUM of HDFC Low Duration?",
    "What is the expense ratio of HDFC Infrastructure Fund?", "What is the benchmark of HDFC Infrastructure Fund?", "What is the NAV of HDFC Infrastructure Fund?",
    "What is the exit load of HDFC Dynamic Debt Fund?", "how much is the expense ratio for hdfc midcap", "flexicap fund NAV today",
    "How risky is HDFC Equity Savings Fund according to the riskometer?", "What is the expense ratio?", "What's the NAV?", "Which benchmark does it track?",
    "Compare HDFC Mid Cap Fund and HDFC Small Cap Fund", "Compare the expense ratio of HDFC Flexi Cap Fund and HDFC Value Fund",
    "HDFC Mid Cap vs HDFC Hybrid Equity Fund exit load", "Compare 1 year returns of HDFC Mid Cap and HDFC Small Cap",
    "Compare returns of HDFC Mid Cap and HDFC Small Cap", "What is the recommended minimum SIP for HDFC Mid Cap Fund?",
    "What is the daily change in NAV of HDFC Small Cap Fund?", "What are the top 3 holdings of HDFC Dynamic Term Fund?",
    "What are the top 3 holdings of HDFC Ultra Short to Short Term Fund?", "What is the minimum investment for HDFC Gold ETF Fund of Fund?",
    "What is the exit load of HDFC Dynamic Term Fund?", "What is the NAV value today?", "gold price today",
]


def test_golden_factual_questions_are_not_refused_or_blocked():
    for q in GOLDEN_FACTUAL:
        assert not advice(q) and not orch.contains_sensitive_info(q), q


# --- PAN written one character at a time --------------------------------------------------------------------

PAN_SPELLED = ["A B C D E 1 2 3 4 F", "A-B-C-D-E 1-2-3-4 F", "a b c d e 1 2 3 4 f", "ABCDE 1 2 3 4 F", "A B C D E 1234 F", "A B C D E1234F",
               "A - B - C - D - E 1 2 3 4 K", "A  B  C  D  E  1  2  3  4  F"]


def test_pan_written_one_character_at_a_time_is_blocked_bare_and_in_a_sentence():
    for pan in PAN_SPELLED:
        for text in (pan, f"PAN number is {pan}", f"my pan is {pan}, what is the NAV of HDFC Value Fund?", f"{pan} show my holdings"):
            assert orch.contains_sensitive_info(text), text


ORDINARY_QUESTIONS = [
    "What is the NAV of HDFC Mid Cap Fund?", "Compare the expense ratio of HDFC Value Fund and HDFC Flexi Cap Fund.",
    "What are the top 3 holdings of HDFC Dynamic Term Fund?", "Rank the funds A B C D E by NAV", "What is the 1 year return of HDFC Small Cap Fund?",
    "In March 2026 I invested in HDFC Mid Cap Fund", "Plan A B C D E options for the funds", "Option 1 2 3 4 for HDFC Value Fund",
    "What was the NAV on 1 2 3 4 days ago?", "I can invest about 5000 a month in HDFC Flexi Cap Fund",
    "Fund A B C and D, E is 1 2 3 4 or F?", "What is the minimum SIP for HDFC Gold ETF Fund of Fund?", "NAV 245.67 on 18 Oct 2026",
    "What is the AUM of HDFC Ultra Short to Short Term Fund in crores?", "Is HDFC Equity Savings Fund an equity or debt fund?",
]


def test_ordinary_fund_questions_are_not_blocked_as_pan():
    assert len(ORDINARY_QUESTIONS) >= 10
    for q in ORDINARY_QUESTIONS:
        assert not orch.contains_sensitive_info(q), q


# --- the real chat(): refused or blocked BEFORE any answer-model call --------------------------------------------

KNOWN_ADVICE_MISSES = [
    "Which fund will give me the highest returns?", "What's the safest HDFC fund to put my parents' money in?",
    "How should I split 50,000 a month across these funds?", "Tell me which fund beats the others and deserves my money.",
    "Mujhe konsa HDFC fund lena chahiye?", "Kya mujhe abhi SIP shuru karni chahiye?", "Is fund mein invest karun ya nahi?",
]
KNOWN_PII_MISS = "PAN number is A B C D E 1 2 3 4 F"


class _NoRetrieval:
    def retrieve(self, *a, **k):
        raise AssertionError("retrieval must not run for a refused or blocked question")


def _chat_with_model_stubbed(query, fund_id=None):
    """Runs the real chat(). The answer model must never be called; the refusal wording (temperature 0.5) falls back to its fixed text."""
    calls = []

    def stub(messages, **kwargs):
        calls.append(kwargs)
        if kwargs.get("temperature") == 0.5:
            return None  # refusal wording: use the fixed fallback reply (still contains the AMFI link)
        raise AssertionError(f"the answer model was called for {query!r}")

    original = orch.chat_completion
    orch.chat_completion = stub
    try:
        return orch.chat(query, retriever=_NoRetrieval(), fund_id=fund_id), calls
    finally:
        orch.chat_completion = original


def test_known_advice_misses_are_refused_on_the_first_reply_before_any_answer_call():
    for q in KNOWN_ADVICE_MISSES:
        result, calls = _chat_with_model_stubbed(q)
        assert result["rejected"] is True and AMFI in result["message"], (q, result["message"][:80])
        assert not result.get("needs_fund_clarification"), q
        assert all(c.get("temperature") == 0.5 for c in calls), f"only the refusal wording may use the model: {q!r}"


def test_known_pan_miss_is_blocked_before_any_model_call():
    result, calls = _chat_with_model_stubbed(KNOWN_PII_MISS)
    assert result["rejected"] is True and PII_MESSAGE in result["message"]
    assert calls == [], "a PII message must never reach the model"


def test_pii_is_blocked_at_the_first_step_and_again_if_the_text_is_re_sent_after_a_fund_pick():
    # The app re-sends the original text to chat() with the chosen fund_id, so the check must hold in both calls.
    for text in (KNOWN_PII_MISS, "my pan is a-b-c-d-e 1-2-3-4 f", "PAN: A B C D E 1 2 3 4 F what is the NAV?"):
        first, calls1 = _chat_with_model_stubbed(text)
        again, calls2 = _chat_with_model_stubbed(text, fund_id="hdfc-value-fund-direct-plan-growth-option-3623")
        for result, calls in ((first, calls1), (again, calls2)):
            assert PII_MESSAGE in result["message"] and calls == []


def test_a_plain_factual_question_without_a_fund_still_asks_which_fund():
    for q in ("What is the expense ratio?", "What's the NAV?", "What is the exit load?"):
        result, calls = _chat_with_model_stubbed(q)
        assert result.get("needs_fund_clarification") is True and calls == [], q


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
