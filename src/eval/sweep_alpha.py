# sweep_alpha.py: tries several hybrid alpha values (retrieval only, no LLM) so you can pick alpha with numbers.
# alpha = 0 -> BM25 keywords only, 1 -> vectors only, in between -> a mix.
# Run from the repo root:  python -m src.eval.sweep_alpha            (or --alphas 0,0.3,0.6)

import argparse                                  # command-line flags
import json                                      # write the results file
from pathlib import Path                         # file paths

from src.eval.metrics import summarize           # aggregate metrics
from src.eval.run_eval import REPORTS_DIR, load_questions, score_retrieval  # reuse the eval building blocks
from src.retrieval.retriever import Retriever    # one Weaviate connection for everything

METRICS = [                                      # (key in summary, column title)
    ("hybrid_section_hit_at_5", "hyb_sec@5"),    # before rerank: this is where alpha matters most
    ("hybrid_mrr", "hyb_MRR"),
    ("recall_at_30", "rec@30"),                  # did the right file even reach the reranker?
    ("section_hit_at_5", "sec@5"),               # after rerank: what the LLM actually sees
    ("mrr", "MRR"),
]


def main() -> None:
    p = argparse.ArgumentParser(description="Compare hybrid alpha values on the golden set.")
    p.add_argument("--alphas", default="0,0.25,0.5,0.75,1", help="comma list of alpha values")
    args = p.parse_args()
    alphas = [float(a) for a in args.alphas.split(",")]

    questions = [q for q in load_questions() if q["type"] != "unanswerable"]  # retrieval needs expected sources
    types = sorted({q["type"] for q in questions})
    results = {}                                              # alpha -> {type -> summary}
    with Retriever() as retriever:
        for alpha in alphas:
            records = [score_retrieval(q, retriever, alpha)[0] for q in questions]  # [0] = metrics, skip chunks
            results[alpha] = {t: summarize([r for r in records if r["type"] == t]) for t in types}
            results[alpha]["ALL"] = summarize(records)
            print(f"alpha={alpha} done")

    for key, title in METRICS:                               # one small table per metric
        print(f"\n{title:<17}" + "".join(f"{'a=' + str(a):>8}" for a in alphas))
        for t in types + ["ALL"]:
            print(f"{t:<17}" + "".join(f"{results[a][t][key]:>8.2f}" for a in alphas))

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / "alpha_sweep.json"
    out.write_text(json.dumps({str(a): v for a, v in results.items()}, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
