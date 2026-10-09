# metrics.py: pure scoring functions for the evaluation (no Weaviate, no Ollama, so they're easy to test).
# "Relevant" always means: the chunk comes from one of the question's expected source FILES.
# We match files rather than doc_ids because RMF v1 and v2 share doc_id INV-RMF-001,
# and citing the superseded v1 file must count as WRONG.

import re                                        # regular expressions
from statistics import mean                      # average of a list of numbers

NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")   # 4012, 1,000, 2.0
WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]+")          # lowercase words like "schema", "err-pipe-4012"
STOPWORDS = {                                         # common words that carry no meaning for overlap
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were", "has", "have", "its",
    "not", "but", "which", "under", "into", "than", "only", "also", "must", "will", "would", "can",
    "there", "their", "they", "been", "being", "per", "any", "all", "each", "other", "when", "what",
}


def is_relevant(source_file: str, expected_files: list[str]) -> bool:
    """True if a chunk's file is one of the expected files.
    Chunks store 'data/investment/x.md'; the golden set stores 'investment/x.md', so compare the ends."""
    return any(source_file.endswith(f) for f in expected_files)


def expected_sections(source_section: str) -> list[str]:
    """'INV-FS-HRGE: Share Classes and Costs; v1.0: 3. Value-at-Risk Limits (step 4)'
    -> ['share classes and costs', '3. value-at-risk limits']"""
    out = []
    for part in source_section.split(";"):                   # several sections are separated by ";"
        part = re.sub(r"^\s*[\w.\-]+:\s*", "", part)          # drop a "DOC-ID:" or "v1.0:" prefix
        part = re.sub(r"\s*\(.*\)\s*$", "", part)              # drop a trailing note like "(step 4)"
        if part.strip():
            out.append(part.strip().lower())
    return out


def section_matches(section: str, text: str, wanted: list[str]) -> bool:
    """True if an expected heading is in the chunk's heading path ('4. Market Risk Limits > 4.1 VaR ...')
    or starts a line of its text (the chunker keeps sub-headings like '2.2 Minimum holding period' in .txt
    files as plain lines, not in the section path)."""
    lines = [line.strip().lower() for line in text.splitlines()]
    return any(w in section.lower() or any(line.startswith(w) for line in lines) for w in wanted)


def hit_at_k(flags: list[bool], k: int) -> float:
    """flags[i] says whether result i is relevant. 1.0 if ANY of the top-k is relevant, else 0.0."""
    return float(any(flags[:k]))


def reciprocal_rank(flags: list[bool]) -> float:
    """1/rank of the first relevant result (1st -> 1.0, 2nd -> 0.5, ...), 0.0 if none. Averaged, this is MRR."""
    for rank, ok in enumerate(flags, start=1):
        if ok:
            return 1.0 / rank
    return 0.0


def recall_at_k(source_files: list[str], expected_files: list[str], k: int) -> float:
    """Fraction of the expected FILES found in the top-k (matters for multi-doc questions)."""
    found = {e for e in expected_files for f in source_files[:k] if f.endswith(e)}  # set = count each file once
    return len(found) / len(set(expected_files))


def numbers_in(text: str) -> set[float]:
    """All numbers in a text as floats ('2.0' == '2')."""
    return {float(n.replace(",", "")) for n in NUMBER_RE.findall(text)}


def content_words(text: str) -> set[str]:
    """Meaningful lowercase words (3+ characters, not stopwords)."""
    return {w for w in WORD_RE.findall(text.lower()) if len(w) >= 3 and w not in STOPWORDS}


def overlap_recall(expected: set, got: set) -> float | None:
    """Share of the expected items that also appear in the answer. None if nothing was expected."""
    if not expected:
        return None
    return len(expected & got) / len(expected)


def number_recall(answer: str, expected_answer: str) -> float | None:
    """Cheap correctness check: share of the expected answer's numbers (2.0, 110, 15) found in our answer."""
    return overlap_recall(numbers_in(expected_answer), numbers_in(answer))


def word_recall(answer: str, expected_answer: str) -> float | None:
    """Cheap correctness check: share of the expected answer's content words found in our answer."""
    return overlap_recall(content_words(expected_answer), content_words(answer))


def avg(values: list) -> float | None:
    """Average that ignores None (= 'not applicable'); None if nothing is left."""
    vals = [v for v in values if v is not None]
    return round(mean(vals), 3) if vals else None


def summarize(records: list[dict]) -> dict:
    """Turn per-question records into one dict of aggregate metrics."""
    answerable = [r for r in records if r["type"] != "unanswerable"]
    unanswerable = [r for r in records if r["type"] == "unanswerable"]
    has_answers = any("refused" in r for r in records)          # False in --retrieval-only runs
    out = {
        "n": len(records),
        "hit_at_5": avg([r.get("hit_at_5") for r in answerable]),                 # right FILE in final top 5
        "recall_at_5": avg([r.get("recall_at_5") for r in answerable]),           # share of expected files in top 5
        "recall_at_30": avg([r.get("recall_at_30") for r in answerable]),         # ... in the 30 hybrid candidates
        "hybrid_section_hit_at_5": avg([r.get("hybrid_section_hit_at_5") for r in answerable]),  # before rerank
        "section_hit_at_5": avg([r.get("section_hit_at_5") for r in answerable]), # right SECTION after rerank
        "hybrid_mrr": avg([r.get("hybrid_rr") for r in answerable]),              # MRR before rerank (top 30)
        "mrr": avg([r.get("rr") for r in answerable]),                            # section-level MRR after rerank
    }
    if has_answers:
        out.update({
            "citation_valid": avg([float(not r["fallback"]) for r in records]),
            "unanswerable_refusal_acc": avg([float(r["refused"]) for r in unanswerable]),
            "wrong_refusal_rate": avg([float(r["refused"]) for r in answerable]),
            "cited_correct_doc": avg([r.get("cited_correct_doc") for r in answerable if not r["refused"]]),
            "number_recall": avg([r.get("number_recall") for r in answerable]),
            "word_recall": avg([r.get("word_recall") for r in answerable]),
            "avg_seconds": avg([r.get("seconds") for r in records]),
        })
    if any(r.get("faithfulness") is not None for r in records):
        out["faithfulness"] = avg([r.get("faithfulness") for r in records])
    return out
