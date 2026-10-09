# test_metrics.py: unit tests for the evaluation metrics (pure functions, no services needed).
# Run from the repo root:  pytest -v tests/test_metrics.py

from src.eval.metrics import (
    expected_sections, hit_at_k, is_relevant, number_recall, recall_at_k,
    reciprocal_rank, section_matches, summarize, word_recall,
)


def test_is_relevant_matches_file_not_doc_id():
    v2 = "data/investment/risk_management_framework_v2.md"
    v1 = "data/investment/risk_management_framework_v1.md"
    expected = ["investment/risk_management_framework_v2.md"]
    assert is_relevant(v2, expected)
    assert not is_relevant(v1, expected)         # same doc_id, but the superseded file must NOT count


def test_hit_and_reciprocal_rank():
    flags = [False, False, True, False]          # first relevant result is at rank 3
    assert hit_at_k(flags, 2) == 0.0
    assert hit_at_k(flags, 3) == 1.0
    assert reciprocal_rank(flags) == 1 / 3
    assert reciprocal_rank([False, False]) == 0.0


def test_recall_counts_each_expected_file_once():
    files = ["data/a.md", "data/a.md", "data/c.md"]
    assert recall_at_k(files, ["a.md", "b.md"], 3) == 0.5   # a found (twice, counted once), b missing


def test_expected_sections_strips_prefixes_and_notes():
    raw = "INV-FS-HRGE: Share Classes and Costs; v1.0: 3. Value-at-Risk Limits (step 4)"
    assert expected_sections(raw) == ["share classes and costs", "3. value-at-risk limits"]


def test_section_matches_path_or_heading_line():
    wanted = ["2.2 minimum holding period"]
    assert section_matches("2. PERSONAL TRADING", "intro\n2.2 Minimum holding period\nHold 30 days.", wanted)
    assert not section_matches("2. PERSONAL TRADING", "See 2.2 Minimum holding period below.", wanted)
    assert section_matches("4. Market Risk Limits > 4.1 VaR Limits", "", ["4.1 var limits"])


def test_number_and_word_recall():
    expected = "2.0% of NAV under RMF v2.0, effective 2026-04-01."
    assert number_recall("The limit is 2% of NAV [1].", expected) < 1.0    # date numbers missing
    assert number_recall("2.0% from 2026-04-01 [1].", expected) == 1.0     # 2.0 == 2, and 2026, 4, 1 found
    assert number_recall("anything", "No numbers here.") is None           # nothing to check
    assert word_recall("schema drift detected", "Schema drift was detected") == 1.0


def test_summarize_ignores_unanswerable_for_retrieval_and_scores_refusals():
    records = [
        {"type": "exact_lookup", "hit_at_5": 1.0, "rr": 0.5, "refused": False, "fallback": False,
         "cited_correct_doc": 1.0},
        {"type": "exact_lookup", "hit_at_5": 0.0, "rr": 0.0, "refused": True, "fallback": True},
        {"type": "unanswerable", "refused": True, "fallback": False},
    ]
    s = summarize(records)
    assert s["hit_at_5"] == 0.5                  # average over the 2 answerable questions only
    assert s["mrr"] == 0.25
    assert s["unanswerable_refusal_acc"] == 1.0
    assert s["wrong_refusal_rate"] == 0.5        # 1 of 2 answerable questions was refused
    assert s["citation_valid"] == round(2 / 3, 3)  # the fallback refusal counts as a citation failure
    assert s["cited_correct_doc"] == 1.0         # refused answers are left out (they cite nothing)
