# compare_demo.py: shows the top 5 BEFORE reranking (hybrid order) and AFTER reranking, for each query.
# Run from the repo root:  python -m src.retrieval.compare_demo
# Or ask your own:         python -m src.retrieval.compare_demo "your question here"

import sys                                       # command-line arguments
import time                                      # timing

from src.rerank.reranker import RERANK_MODEL, get_model, rerank  # the reranker
from src.retrieval.retriever import Retriever    # hybrid search

QUERIES = [
    "What does ERR-PIPE-4012 mean?",                                  # exact error code
    "What is the current equity VaR limit?",                          # uses the policy's own words
    "How much can we lose before we have to cut risk?",              # plain-English paraphrase, no keywords
    "What happens if the incoming data has new unexpected columns?",  # describes schema drift without naming it
]
CANDIDATES = 30                                  # how many hybrid results we hand to the reranker
TOP_N = 5                                        # how many we show / would send to the LLM


def show(title: str, results, score_attr: str) -> None:
    """Print one block of results with the chosen score."""
    print(f"  {title}")
    for rank, r in enumerate(results, start=1):
        score = getattr(r, score_attr)           # getattr reads r.score or r.rerank_score by name
        print(f"    {rank}. {score:6.3f}  {r.chunk_id:<26} {r.section[:55]}")


def main() -> None:
    queries = sys.argv[1:] or QUERIES            # your question if given, else the default list

    t0 = time.perf_counter()
    get_model()                                  # load the reranker up front so we can time it separately
    print(f"Reranker {RERANK_MODEL} loaded in {time.perf_counter() - t0:.1f}s")

    with Retriever() as retriever:               # one connection for all queries
        for q in queries:
            candidates = retriever.retrieve(q, k=CANDIDATES)          # step 1: broad, fast hybrid search
            t0 = time.perf_counter()
            reranked = rerank(q, candidates, top_n=TOP_N)             # step 2: precise, slower reranking
            ms = (time.perf_counter() - t0) * 1000                    # milliseconds
            print(f"\nQ: {q}   ({len(candidates)} candidates reranked in {ms:.0f} ms)")
            show("BEFORE (hybrid score)", candidates[:TOP_N], "score")
            show("AFTER  (rerank score)", reranked, "rerank_score")


if __name__ == "__main__":
    main()
