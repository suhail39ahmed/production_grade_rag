# search_demo.py: runs hybrid (keyword + vector) searches against the DocChunk collection.
# Run from the repo root after indexing:  python -m src.retrieval.search_demo
# Or ask your own question:               python -m src.retrieval.search_demo "your question here"

import sys                                          # gives access to command-line arguments

import weaviate                                     # Weaviate client (v4)
from weaviate.classes.query import Filter, MetadataQuery  # Filter = WHERE clause; MetadataQuery = ask for scores

from src.ingest.indexer import COLLECTION_NAME, get_embedder  # reuse the SAME embedder and name as indexing

DEFAULT_QUERIES = [
    "What does ERR-PIPE-4012 mean?",                # exact error code: keyword (BM25) search shines here
    "What is the current equity VaR limit?",        # meaning-based question: vector search helps here
]


def hybrid_search(collection, embedder, query: str, limit: int = 5, alpha: float = 0.5):
    """Search with BM25 + vectors combined, skipping superseded documents."""
    query_vector = embedder.embed_query(query)       # embed the question with the same model as the chunks
    return collection.query.hybrid(
        query=query,                                 # the raw text, used for BM25 keyword matching
        vector=query_vector,                         # our own query vector (the collection has no vectorizer)
        alpha=alpha,                                 # 0 = keywords only, 1 = vectors only, 0.5 = equal mix
        limit=limit,                                 # how many results to return
        filters=Filter.by_property("status").not_equal("superseded"),  # drop old policy versions
        return_metadata=MetadataQuery(score=True, explain_score=True),  # include scores in the results
    )


def print_results(query: str, response) -> None:
    """Print one line per result: rank, score, chunk_id, section."""
    print(f"\nQ: {query}")
    for rank, obj in enumerate(response.objects, start=1):  # enumerate gives 1, 2, 3... alongside each result
        p = obj.properties                                 # the stored fields of this chunk
        print(f"  {rank}. {obj.metadata.score:.3f}  {p['chunk_id']:<26} {p['section'][:60]}")


def main() -> None:
    queries = sys.argv[1:] or DEFAULT_QUERIES               # use the command-line question if given, else the defaults
    embedder = get_embedder()
    with weaviate.connect_to_local() as client:             # connection closes automatically at the end
        collection = client.collections.get(COLLECTION_NAME)
        for q in queries:
            print_results(q, hybrid_search(collection, embedder, q))


if __name__ == "__main__":
    main()
