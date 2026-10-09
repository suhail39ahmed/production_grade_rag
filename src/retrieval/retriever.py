# retriever.py: hybrid (BM25 + vector) search over the DocChunk collection, returning simple results.
# Usage:
#     with Retriever() as r:                     # opens ONE Weaviate connection
#         results = r.retrieve("What does ERR-PIPE-4012 mean?")
#     # the connection is closed here automatically

from dataclasses import dataclass                # simple data-holding classes

import weaviate                                  # Weaviate client (v4)
from weaviate.classes.query import Filter, MetadataQuery  # Filter = WHERE clause; MetadataQuery = ask for scores

from src.ingest.indexer import COLLECTION_NAME, get_embedder  # same collection name and embedder as indexing


@dataclass
class SearchResult:
    """One retrieved chunk, in a plain shape the rest of the app can use."""
    chunk_id: str                                # e.g. TECH-RB-001::v2.3::003, used for citations
    text: str                                    # breadcrumb + chunk text
    doc_id: str                                  # e.g. TECH-RB-001
    version: str                                 # e.g. 2.3
    section: str                                 # heading path inside the document
    source_file: str                             # where the chunk came from
    score: float                                 # hybrid score from Weaviate (0..1, higher = better)
    rerank_score: float | None = None            # filled in later by the reranker (None until then)


class Retriever:
    """Holds one Weaviate connection and one embedder, and reuses them for every query."""

    def __init__(self):
        self.client = weaviate.connect_to_local()                     # localhost:8080 (HTTP) + 50051 (gRPC)
        self.collection = self.client.collections.get(COLLECTION_NAME)  # handle to our chunks
        self.embedder = get_embedder()                                # bge-m3 via Ollama

    def retrieve(self, query: str, k: int = 30, alpha: float = 0.5) -> list[SearchResult]:
        """Return the top-k chunks for a query, never from superseded documents."""
        response = self.collection.query.hybrid(
            query=query,                                              # raw text, used for BM25 keyword matching
            vector=self.embedder.embed_query(query),                  # query vector from the SAME model as the chunks
            alpha=alpha,                                              # 0 = keywords only, 1 = vectors only
            limit=k,                                                  # how many candidates to return
            filters=Filter.by_property("status").not_equal("superseded"),  # skip old versions (keeps "accepted" ADRs)
            return_metadata=MetadataQuery(score=True),                # we want the hybrid score back
        )
        return [                                                      # convert each Weaviate object to a SearchResult
            SearchResult(
                chunk_id=o.properties["chunk_id"],
                text=o.properties["text"],
                doc_id=o.properties["doc_id"],
                version=o.properties["version"],
                section=o.properties["section"],
                source_file=o.properties["source_file"],
                score=o.metadata.score,
            )
            for o in response.objects
        ]

    def close(self) -> None:
        """Close the Weaviate connection (call this when you're done)."""
        self.client.close()

    def __enter__(self):                         # runs at the start of a "with Retriever() as r:" block
        return self                              # "r" becomes this Retriever

    def __exit__(self, *exc):                    # runs at the end of the "with" block, even after an error
        self.close()                             # so the connection is never left open
