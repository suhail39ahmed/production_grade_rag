# reranker.py: re-scores retrieved chunks with a cross-encoder so the best answers come first.
# A cross-encoder reads the question AND the chunk together, which is slower but much more accurate
# than comparing two separate vectors. So we use it only on the ~30 candidates hybrid search returns.

import os                                        # reads environment variables (settings)
from dataclasses import replace                  # copies a dataclass while changing some fields
from functools import lru_cache                  # remembers a function's result so it only runs once

from dotenv import load_dotenv                   # loads settings from a .env file
from sentence_transformers import CrossEncoder   # the cross-encoder model wrapper

from src.retrieval.retriever import SearchResult  # the result shape we rerank

load_dotenv()                                    # read .env so os.getenv sees its values

RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")  # which model to use (override in .env)
MAX_LENGTH = 512                                 # max tokens per (question + chunk) pair; longer pairs are cut


@lru_cache(maxsize=None)                         # remembers one loaded model per model name
def _load_model(model_name: str) -> CrossEncoder:
    """Load a cross-encoder (downloads it the first time, then reads it from the HF cache)."""
    return CrossEncoder(model_name, max_length=MAX_LENGTH)  # uses the GPU if there is one, otherwise CPU


def get_model(model_name: str = RERANK_MODEL) -> CrossEncoder:
    """Return the cached model. Always passes the name explicitly, so the cache key is the same
    whether you call get_model() or get_model("BAAI/bge-reranker-v2-m3")."""
    return _load_model(model_name)


def rerank(query: str, candidates: list[SearchResult], top_n: int = 5,
           model_name: str = RERANK_MODEL) -> list[SearchResult]:
    """Score every candidate against the query and return the top_n, best first."""
    if not candidates:                                           # nothing to rerank
        return []
    model = get_model(model_name)                                # cached after the first call
    pairs = [(query, c.text) for c in candidates]                # the model reads (question, chunk) together
    scores = model.predict(pairs, batch_size=16)                 # one relevance score per pair (higher = better)
    # Note: bge rerankers give 0..1 scores; ms-marco MiniLM gives raw scores that can be negative.
    # Only the ORDER matters here, so both work the same way.
    scored = [replace(c, rerank_score=float(s))                  # copy each result with its new score...
              for c, s in zip(candidates, scores)]               # ...so the caller's list isn't modified
    scored.sort(key=lambda c: c.rerank_score, reverse=True)      # best score first
    return scored[:top_n]                                        # keep only the top_n
