# run_eval.py: runs the golden questions through the pipeline and scores retrieval, citations, refusals.
# Run from the repo root:
#   python -m src.eval.run_eval --retrieval-only           # fast: no LLM (about a minute)
#   python -m src.eval.run_eval --limit 5                  # first 5 questions, full pipeline
#   python -m src.eval.run_eval --types unanswerable,semantic --ragas
#   python -m src.eval.run_eval --resume                   # continue a run that was interrupted

import argparse                                  # command-line flags
import json                                      # read/write JSON
import os                                        # environment variables
import time                                      # timing
from datetime import datetime                    # timestamps for report names
from pathlib import Path                         # file paths

from src.eval.metrics import (                   # our pure scoring functions
    expected_sections, hit_at_k, is_relevant, number_recall, recall_at_k, reciprocal_rank,
    section_matches, summarize, word_recall,
)
from src.generate.answer import CHAT_MODEL, generate, get_llm  # generation step from Phase 4
from src.rerank.reranker import RERANK_MODEL, rerank          # Phase 3 reranker
from src.retrieval.retriever import Retriever                 # Phase 3 retriever

GOLDEN_PATH = Path("eval/golden_qa.jsonl")       # one JSON question per line
REPORTS_DIR = Path("reports")                    # where results are written
PARTIAL_PATH = REPORTS_DIR / "partial.jsonl"     # progress file, so an interrupted run can --resume
CANDIDATES, TOP_N = 30, 5                        # same settings as the real pipeline


def load_questions(ids=None, types=None, limit=None) -> list[dict]:
    """Read the golden set and keep only the questions selected by the flags."""
    with GOLDEN_PATH.open(encoding="utf-8") as f:            # "with" closes the file automatically
        questions = [json.loads(line) for line in f if line.strip()]
    if ids:
        questions = [q for q in questions if q["id"] in ids]
    if types:
        questions = [q for q in questions if q["type"] in types]
    return questions[:limit] if limit else questions        # [:None] would also work, but this is clearer


def score_retrieval(q: dict, retriever: Retriever, alpha: float):
    """Retrieve + rerank one question; return (metrics dict, the 5 reranked chunks)."""
    t0 = time.perf_counter()
    candidates = retriever.retrieve(q["question"], k=CANDIDATES, alpha=alpha)  # hybrid top 30
    chunks = rerank(q["question"], candidates, top_n=TOP_N)                    # reranked top 5
    rec = {
        "id": q["id"], "type": q["type"], "question": q["question"],
        "top5": [c.chunk_id for c in chunks],                # what the LLM will see
        "retrieval_seconds": round(time.perf_counter() - t0, 2),
    }
    expected = q["source_files"]
    if expected:                                             # unanswerable questions have no expected files
        wanted = expected_sections(q["source_section"])      # e.g. ["4.1 var and expected shortfall limits"]
        # A result is "relevant" if it comes from an expected file AND sits under an expected section.
        relevant = lambda c: is_relevant(c.source_file, expected) and section_matches(c.section, c.text, wanted)
        hybrid_flags = [relevant(c) for c in candidates]     # before rerank (30 results)
        final_flags = [relevant(c) for c in chunks]          # after rerank (5 results)
        final_files = [c.source_file for c in chunks]
        rec.update({
            "hit_at_5": float(any(is_relevant(f, expected) for f in final_files)),  # file level (easy)
            "recall_at_5": recall_at_k(final_files, expected, 5),
            "recall_at_30": recall_at_k([c.source_file for c in candidates], expected, CANDIDATES),
            "hybrid_section_hit_at_5": hit_at_k(hybrid_flags, 5),
            "section_hit_at_5": hit_at_k(final_flags, 5),   # section level (the real test)
            "hybrid_rr": reciprocal_rank(hybrid_flags),     # same, but before rerank (shows what alpha does)
            "rr": reciprocal_rank(final_flags),             # averaged later into MRR
        })
    return rec, chunks


def score_answer(q: dict, chunks, llm) -> dict:
    """Generate an answer from the given chunks and score it."""
    a = generate(q["question"], chunks, llm)                 # LLM + citation check + retry
    rec = {
        "answer": a.text,
        "refused": a.refused,
        "fallback": a.fallback,                              # refused only because the checks kept failing
        "attempts": a.attempts,
        "check_errors": a.check_errors,
        "cited": [s.chunk_id for s in a.sources],
        "generate_seconds": round(a.timings["generate"], 2),
        "contexts": [c.text for c in chunks],                # kept for the optional ragas judge
    }
    if q["type"] != "unanswerable":
        rec["cited_correct_doc"] = (float(any(is_relevant(s.source_file, q["source_files"]) for s in a.sources))
                                    if not a.refused else None)  # None = not applicable (nothing cited)
        rec["number_recall"] = number_recall(a.text, q["expected_answer"])
        rec["word_recall"] = word_recall(a.text, q["expected_answer"])
    return rec


def load_partial() -> dict:
    """Read finished questions from an interrupted run. Later lines win (they may add ragas scores)."""
    if not PARTIAL_PATH.exists():
        return {}
    with PARTIAL_PATH.open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}      # dict keyed by question id


def save_partial(rec: dict) -> None:
    """Append one finished question to the progress file."""
    with PARTIAL_PATH.open("a", encoding="utf-8") as f:      # "a" = append
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fmt(v) -> str:
    """Format a metric for the table: 0.857 -> '0.86', None -> '-'."""
    return "-" if v is None else f"{v:.2f}"


def print_summary(records: list[dict], overall: dict) -> None:
    """Print one row per question type plus an ALL row."""
    cols = ["hit_at_5", "recall_at_5", "recall_at_30", "hybrid_section_hit_at_5", "section_hit_at_5", "mrr"]
    if "citation_valid" in overall:
        cols += ["citation_valid", "unanswerable_refusal_acc", "wrong_refusal_rate",
                 "cited_correct_doc", "number_recall", "avg_seconds"]
    if "faithfulness" in overall:
        cols.append("faithfulness")
    short = {"hit_at_5": "file@5", "recall_at_5": "rec@5", "recall_at_30": "rec@30",
             "hybrid_section_hit_at_5": "hyb_sec@5", "section_hit_at_5": "sec@5", "mrr": "MRR",
             "citation_valid": "cit_ok", "unanswerable_refusal_acc": "unans_ref",
             "wrong_refusal_rate": "wrong_ref", "cited_correct_doc": "cite_doc",
             "number_recall": "num_rec", "avg_seconds": "s/q", "faithfulness": "faith"}
    print(f"\n{'type':<17}{'n':>3} " + "".join(f"{short[c]:>10}" for c in cols))
    types = sorted({r["type"] for r in records})
    for t in types + ["ALL"]:
        group = records if t == "ALL" else [r for r in records if r["type"] == t]
        s = overall if t == "ALL" else summarize(group)
        print(f"{t:<17}{len(group):>3} " + "".join(f"{fmt(s.get(c)):>10}" for c in cols))


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate the RAG pipeline on the golden set.")
    p.add_argument("--limit", type=int, help="only the first N selected questions")
    p.add_argument("--types", help="comma list, e.g. exact_lookup,semantic")
    p.add_argument("--ids", help="comma list, e.g. q001,q005")
    p.add_argument("--retrieval-only", action="store_true", help="skip the LLM: retrieval metrics only (fast)")
    p.add_argument("--ragas", action="store_true", help="also score faithfulness with a local LLM judge (slow)")
    p.add_argument("--alpha", type=float, default=0.5, help="hybrid weight: 0 = BM25 only, 1 = vectors only")
    p.add_argument("--resume", action="store_true", help="skip questions already in reports/partial.jsonl")
    p.add_argument("--out", help="report path (default reports/eval_<timestamp>.json)")
    args = p.parse_args()
    split = lambda s: s.split(",") if s else None            # "a,b" -> ["a", "b"]; None stays None

    questions = load_questions(split(args.ids), split(args.types), args.limit)
    REPORTS_DIR.mkdir(exist_ok=True)                         # create reports/ if missing
    done = load_partial() if args.resume else {}
    if not args.resume:
        PARTIAL_PATH.unlink(missing_ok=True)                 # fresh run: forget old progress
    mode = "retrieval-only" if args.retrieval_only else "full"
    print(f"Evaluating {len(questions)} questions | mode={mode} alpha={args.alpha} "
          f"rerank={RERANK_MODEL} llm={'-' if args.retrieval_only else CHAT_MODEL} | resumed {len(done)}")

    llm = None if args.retrieval_only else get_llm()         # one LLM client for all questions
    t_start = time.perf_counter()
    records = []
    with Retriever() as retriever:                           # one Weaviate connection for all questions
        for i, q in enumerate(questions, start=1):
            if q["id"] in done:                              # finished in an earlier run
                records.append(done[q["id"]])
                continue
            t0 = time.perf_counter()
            rec, chunks = score_retrieval(q, retriever, args.alpha)
            if llm:
                rec.update(score_answer(q, chunks, llm))
            rec["seconds"] = round(time.perf_counter() - t0, 1)
            records.append(rec)
            save_partial(rec)                                # progress is saved after EVERY question
            status = "" if not llm else (" REFUSED" if rec["refused"] else " answered") + \
                     (" (fallback)" if rec["fallback"] else "") + f" attempts={rec['attempts']}"
            print(f"[{i:>2}/{len(questions)}] {q['id']} {q['type']:<16} sec@5={fmt(rec.get('section_hit_at_5'))} "
                  f"rr={fmt(rec.get('rr'))}{status}  {rec['seconds']}s", flush=True)  # flush = show it now

    if args.ragas and llm:                                   # judge AFTER all answers, so Ollama loads the judge once
        from src.eval.ragas_judge import make_faithfulness, faithfulness_score  # heavy import only when needed
        metric = make_faithfulness()
        todo = [r for r in records if not r["refused"] and r.get("faithfulness") is None]
        print(f"\nRagas faithfulness for {len(todo)} answered questions (refusals have no claims to judge)")
        for i, r in enumerate(todo, start=1):
            t0 = time.perf_counter()
            r["faithfulness"] = faithfulness_score(metric, r["question"], r["answer"], r["contexts"])
            r["judge_seconds"] = round(time.perf_counter() - t0, 1)
            save_partial(r)
            print(f"[{i:>2}/{len(todo)}] {r['id']} faithfulness={fmt(r['faithfulness'])}  {r['judge_seconds']}s",
                  flush=True)

    overall = summarize(records)
    by_type = {t: summarize([r for r in records if r["type"] == t]) for t in sorted({r["type"] for r in records})}
    report = {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "mode": mode, "alpha": args.alpha, "ragas": args.ragas,
            "rerank_model": RERANK_MODEL, "chat_model": None if args.retrieval_only else CHAT_MODEL,
            "embed_model": os.getenv("EMBED_MODEL", "bge-m3"),
            "n_questions": len(records), "elapsed_seconds": round(time.perf_counter() - t_start, 1),
        },
        "summary": overall,
        "by_type": by_type,
        "questions": records,
    }
    out = Path(args.out) if args.out else REPORTS_DIR / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    for path in (out, REPORTS_DIR / "latest.json"):          # timestamped copy + a fixed name for the CI gate
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print_summary(records, overall)
    print(f"\nTotal {report['run']['elapsed_seconds']}s | report: {out} (also reports/latest.json)")


if __name__ == "__main__":
    main()
