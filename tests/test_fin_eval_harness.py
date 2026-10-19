"""
Offline tests (no network, no Groq) for the eval harness: the report path with simulated rate limits and latencies
(the path that crashed on a variable-name clash), results saved as the run goes, --resume, the cooldown re-run
(first attempts are kept, never silently replaced), and pacing.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIN_EVAL = str(PROJECT_ROOT / "fin_eval.py")


def run(out, *flags, env=None, timeout=300):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, FIN_EVAL, "--out", str(out), *flags], capture_output=True, text=True,
                       timeout=timeout, cwd=str(PROJECT_ROOT), env=e)
    return r


def sim(out, *extra, **kw):
    return run(out, "--simulate-llm", "--delay", "0", "--cooldown", "0", *extra, **kw)


def load(out):
    results = json.loads((Path(out) / "fin_eval_results.json").read_text())
    partial = [json.loads(ln) for ln in (Path(out) / "fin_eval_results.partial.jsonl").read_text().splitlines() if ln.strip()]
    report = (Path(out) / "fin_eval_report.md").read_text() if (Path(out) / "fin_eval_report.md").exists() else ""
    return results, partial, report


def test_full_mode_report_runs_with_simulated_rate_limits_and_latencies():
    with tempfile.TemporaryDirectory() as out:
        r = sim(out)
        assert r.returncode == 0, r.stderr[-800:]
        results, partial, report = load(out)
    assert len(results) == 77 and [x["id"] for x in results] == list(range(1, 78))
    for section in ("## Answer quality (full run)", "## Hallucination", "## Latency", "## Rate limiting (Groq)", "## Failures"):
        assert section in report, section
    assert "Cases rate-limited on first attempt" in report and ": 3 of 77" in report
    assert "Cases re-run once after cooldown: 3 | recovered: 2 | still failing after the re-run: 1" in report
    assert "tokens per minute (TPM)" in report and "org_SIM" not in report  # the 429 text is reported, the organisation id is masked
    assert any(x["latency_s"] > 0 and x["llm_s"] > 0 for x in results)       # simulated latencies reach the report


def test_a_rate_limited_first_attempt_is_kept_and_never_silently_replaced():
    with tempfile.TemporaryDirectory() as out:
        sim(out)
        results, partial, _ = load(out)
    by_id = {x["id"]: x for x in results}
    recovered, again = by_id[3], by_id[15]
    assert recovered["attempt"] == 2 and recovered["rl_final"] is False
    fa = recovered["first_attempt"]
    assert fa["rate_limited"] is True and "couldn't generate a response" in fa["message"] and fa["ok"] is False
    assert again["attempt"] == 2 and again["rl_final"] is True and again["first_attempt"]["rate_limited"] is True
    assert all(x["first_attempt"] is None and x["attempt"] == 1 for x in results if x["id"] not in (3, 9, 15))
    # the partial file holds both attempts of a re-run case, in order
    lines = [p for p in partial if p.get("type") == "case" and p["id"] == 3]
    assert [p["result"]["attempt"] for p in lines] == [1, 2] and lines[0]["result"]["rl_final"] is True


def test_every_case_is_saved_as_soon_as_it_finishes_with_answer_context_timings_and_error_type():
    with tempfile.TemporaryDirectory() as out:
        sim(out)
        _, partial, _ = load(out)
    assert partial[0]["type"] == "header" and partial[0]["n_cases"] == 77 and len(partial[0]["funds_sha256"]) == 64
    cases = [p for p in partial if p["type"] == "case"]
    assert len(cases) == 77 + 3                                    # one line per attempt
    for p in cases:
        assert p["answer_full"] is not None and isinstance(p["context_full"], list) and p["saved_at"]
        res = p["result"]
        assert {"latency_s", "retrieval_s", "llm_s", "error_type", "rl_final", "http_429", "attempt"} <= set(res)
    failed = [p for p in cases if p["result"]["rl_final"]][0]["result"]
    assert failed["error_type"] == "RateLimitError"


def test_saved_results_survive_a_crash_in_the_report_step():
    with tempfile.TemporaryDirectory() as out:
        r = sim(out, env={"FIN_EVAL_TEST_CRASH_IN_REPORT": "1"})
        assert r.returncode != 0 and "simulated crash while building the report" in r.stderr
        assert not (Path(out) / "fin_eval_report.md").exists()
        results = json.loads((Path(out) / "fin_eval_results.json").read_text())
        assert len(results) == 77
        # and --resume rebuilds the report from the saved results without running any case again
        r2 = sim(out, "--resume")
        assert r2.returncode == 0, r2.stderr[-500:]
        assert r2.stderr.count("saved answer reused") >= 74 and (Path(out) / "fin_eval_report.md").exists()


def test_resume_reuses_valid_cases_and_reruns_only_the_missing_or_rate_limited_ones():
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as out:
        sim(src)
        lines = (Path(src) / "fin_eval_results.partial.jsonl").read_text().splitlines()
        header, cases = lines[0], [json.loads(ln) for ln in lines[1:]]
        first_30 = [c for c in cases if c["id"] <= 30 and c["result"]["attempt"] == 1]     # as if the run stopped after case 30
        assert {c["id"] for c in first_30 if c["result"]["rl_final"]} == {3, 9, 15}
        (Path(out) / "fin_eval_results.partial.jsonl").write_text("\n".join([header] + [json.dumps(c) for c in first_30]) + "\n")
        r = sim(out, "--resume")
        assert r.returncode == 0, r.stderr[-600:]
        results, partial, report = load(out)
    assert r.stderr.count("saved answer reused") == 27                      # 30 saved, 3 of them rate-limited
    assert len(results) == 77 and all(x is not None for x in results)
    for i in (3, 9, 15):
        res = results[i - 1]
        assert res["first_attempt"] and res["first_attempt"]["rate_limited"] and res["attempt"] >= 2
    assert "Cases re-run once after cooldown" in report


def test_resume_refuses_results_from_a_different_run():
    with tempfile.TemporaryDirectory() as out:
        sim(out)
        path = Path(out) / "fin_eval_results.partial.jsonl"
        lines = path.read_text().splitlines()
        header = json.loads(lines[0]); header["funds_sha256"] = "0" * 64
        path.write_text("\n".join([json.dumps(header)] + lines[1:]) + "\n")
        r = sim(out, "--resume")
        assert r.returncode != 0 and "different run" in (r.stderr + r.stdout) and "funds_sha256" in (r.stderr + r.stdout)
    with tempfile.TemporaryDirectory() as empty:
        r = sim(empty, "--resume")
        assert r.returncode != 0 and "no saved results" in (r.stderr + r.stdout)


def test_a_fresh_run_keeps_an_older_partial_file_instead_of_overwriting_it():
    with tempfile.TemporaryDirectory() as out:
        sim(out)
        sim(out)
        names = sorted(p.name for p in Path(out).iterdir())
    assert any(n.startswith("fin_eval_results.partial.prev-") for n in names), names


def test_pacing_waits_only_after_cases_that_called_the_llm_and_offline_never_waits():
    with tempfile.TemporaryDirectory() as out:
        t = time.time(); r = run(out, "--simulate-llm", "--delay", "0.1", "--cooldown", "1.5"); paced = time.time() - t
        assert r.returncode == 0, r.stderr[-500:]
        results, _, _ = load(out)
    with tempfile.TemporaryDirectory() as out:
        t = time.time(); sim(out); unpaced = time.time() - t
    llm_cases = sum(1 for x in results if x["llm_calls"] > 0)
    assert 40 < llm_cases < 77                                             # clarify, PII and greeting cases make no LLM call
    assert paced - unpaced >= (llm_cases - 1) * 0.1 * 0.7 + 1.5 * 0.9, (paced, unpaced, llm_cases)  # delays + one cooldown
    with tempfile.TemporaryDirectory() as out:
        t = time.time(); r = run(out, "--offline", "--delay", "100", "--cooldown", "100")
        assert r.returncode == 0 and time.time() - t < 120                 # a 100 s delay per case would take hours
        assert "Original 70 questions: **70/70" in (Path(out) / "fin_eval_report.md").read_text()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
