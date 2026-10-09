# test_gate.py: unit tests for the CI gate and the Markdown summary (no services needed).
# Run from the repo root:  pytest -v tests/test_gate.py

from src.eval.check_gate import evaluate, failure_messages, parse_only
from src.eval.summary_md import to_markdown

THRESHOLDS = {"hit_at_5": {"min": 0.95}, "mrr": {"min": 0.8}, "wrong_refusal_rate": {"max": 0.2},
              "faithfulness": {"min": 0.8}}


def statuses(rows):
    """{metric: status} for easy asserts."""
    return {r["metric"]: r["status"] for r in rows}


def test_pass_fail_and_skip():
    summary = {"hit_at_5": 1.0, "mrr": 0.7, "wrong_refusal_rate": 0.1}   # no faithfulness in this run
    s = statuses(evaluate(summary, THRESHOLDS))
    assert s == {"hit_at_5": "PASS", "mrr": "FAIL", "wrong_refusal_rate": "PASS", "faithfulness": "SKIP"}


def test_max_rule_fails_when_above():
    s = statuses(evaluate({"wrong_refusal_rate": 0.3}, THRESHOLDS, only=["wrong_refusal_rate"]))
    assert s["wrong_refusal_rate"] == "FAIL"


def test_only_checks_listed_metrics_and_requires_them():
    rows = evaluate({"hit_at_5": 1.0}, THRESHOLDS, only=["hit_at_5", "mrr"])
    assert statuses(rows) == {"hit_at_5": "PASS", "mrr": "FAIL"}         # mrr missing -> FAIL, not SKIP
    assert "missing" in failure_messages(rows)[0]


def test_unknown_metric_in_only_fails():
    assert statuses(evaluate({}, THRESHOLDS, only=["hit_at_50"]))["hit_at_50"] == "FAIL"  # typo -> loud failure


def test_parse_only_expands_groups():
    names = parse_only("retrieval,faithfulness")
    assert "section_hit_at_5" in names and names[-1] == "faithfulness"
    assert parse_only(None) is None


def test_markdown_table():
    report = {
        "run": {"mode": "retrieval-only", "n_questions": 2, "alpha": 0.5, "rerank_model": "m",
                "chat_model": None, "elapsed_seconds": 1.0},
        "summary": {"hit_at_5": 1.0, "mrr": 0.5},
        "by_type": {"exact_lookup": {"n": 2, "hit_at_5": 1.0, "mrr": 0.5}},
    }
    md = to_markdown(report, THRESHOLDS, only=["hit_at_5", "mrr"])
    assert "❌ gate FAILED" in md                          # mrr 0.5 < 0.8
    assert "| `hit_at_5` | 1.000 | min 0.95 | ✅ PASS |" in md
    assert "| exact_lookup | 2 | 1.00 | 0.50 |" in md
