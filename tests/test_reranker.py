# test_reranker.py: checks the reranker with tiny made-up inputs (no Weaviate or Ollama needed).
# Run from the repo root:  pytest -v tests/test_reranker.py
# Note: the first run downloads the reranker model, so it can take a few minutes.

from src.rerank.reranker import rerank           # the function under test
from src.retrieval.retriever import SearchResult  # the input/output shape


def make(chunk_id: str, text: str, score: float = 0.5) -> SearchResult:
    """Build a fake SearchResult with only the fields the test cares about."""
    return SearchResult(chunk_id=chunk_id, text=text, doc_id="TEST", version="1.0",
                        section="", source_file="", score=score)


# Three fake chunks: one clearly answers the question, two are off-topic.
CANDIDATES = [
    make("lunch", "The office cafeteria serves lunch from 12:00 to 14:00 on weekdays.", score=0.9),
    make("vpn", "To reset your VPN password, open the IT portal and choose 'Forgot password'.", score=0.8),
    make("schema", "ERR-PIPE-4012 means schema drift was detected: the incoming file has columns "
                   "that are not in the expected Bronze schema, so ingestion is paused.", score=0.1),
]
QUERY = "What does error ERR-PIPE-4012 mean?"


def test_relevant_passage_ranks_first():
    results = rerank(QUERY, CANDIDATES, top_n=3)
    assert results[0].chunk_id == "schema"       # lowest hybrid score, but clearly the right answer


def test_returns_top_n_sorted_by_score():
    results = rerank(QUERY, CANDIDATES, top_n=2)
    assert len(results) == 2                     # exactly top_n results come back
    scores = [r.rerank_score for r in results]
    assert scores == sorted(scores, reverse=True)  # best first
    assert all(isinstance(s, float) for s in scores)  # every result got a real score


def test_does_not_modify_input_and_handles_empty():
    rerank(QUERY, CANDIDATES, top_n=3)
    assert all(c.rerank_score is None for c in CANDIDATES)  # the original list was left untouched
    assert rerank(QUERY, [], top_n=5) == []      # no candidates -> empty list, no crash
