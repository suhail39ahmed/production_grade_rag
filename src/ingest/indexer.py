# indexer.py: embeds every chunk with bge-m3 (via Ollama) and stores it in Weaviate.
# Run from the repo root:  python -m src.ingest.indexer            (upsert, safe to re-run)
#                          python -m src.ingest.indexer --recreate (drop the collection and rebuild)

import argparse                                  # reads command-line flags like --recreate
import os                                        # reads environment variables (settings)
import time                                      # measures how long embedding and inserting take

import weaviate                                  # the Weaviate Python client (v4)
from dotenv import load_dotenv                   # loads settings from a .env file into environment variables
from langchain_ollama import OllamaEmbeddings    # LangChain wrapper that asks Ollama to turn text into vectors
from weaviate.classes.config import (            # building blocks for defining a collection's schema
    Configure,                                   # vector settings (we bring our own vectors)
    DataType,                                    # property types, e.g. TEXT, INT
    Property,                                    # one field on each stored object
    Tokenization,                                # how text is split into words for keyword (BM25) search
)
from weaviate.util import generate_uuid5         # turns any string into a stable, repeatable UUID

from src.ingest.chunker import Chunk, chunk_corpus  # our Phase 1 chunker
from src.ingest.loaders import load_corpus          # our Phase 1 loaders

load_dotenv()                                    # read .env (if it exists) so os.getenv sees its values

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")  # where Ollama listens
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")                           # which embedding model to use
COLLECTION_NAME = "DocChunk"                     # Weaviate's name for our "table" of chunks
EMBED_BATCH_SIZE = 32                            # how many chunks we send to Ollama in one request


def get_embedder() -> OllamaEmbeddings:
    """Create the embedding client. The same one must be used for indexing AND for queries."""
    return OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)  # it only talks to Ollama when used


def ensure_collection(client: weaviate.WeaviateClient, recreate: bool = False):
    """Return the DocChunk collection, creating it (or rebuilding it) if needed."""
    if recreate and client.collections.exists(COLLECTION_NAME):  # --recreate was passed and it already exists...
        client.collections.delete(COLLECTION_NAME)               # ...so drop it and every object inside
        print(f"Deleted existing collection '{COLLECTION_NAME}'")
    if client.collections.exists(COLLECTION_NAME):               # already there: reuse it as-is
        return client.collections.get(COLLECTION_NAME)

    field = Tokenization.FIELD  # FIELD = whole value is ONE token, so "TECH-RB-001" is matched exactly, never split
    word = Tokenization.WORD    # WORD = split on anything that isn't a letter or digit, lowercased: good for BM25
    client.collections.create(
        name=COLLECTION_NAME,
        vector_config=Configure.Vectors.self_provided(),         # no built-in vectorizer: WE send every vector
        properties=[
            Property(name="text", data_type=DataType.TEXT, tokenization=word),         # the chunk text, keyword-searchable
            Property(name="chunk_id", data_type=DataType.TEXT, tokenization=field),    # e.g. TECH-RB-001::v2.3::002
            Property(name="doc_id", data_type=DataType.TEXT, tokenization=field),      # e.g. INV-RMF-001
            Property(name="version", data_type=DataType.TEXT, tokenization=field),     # "2.0" stays "2.0", not "2" and "0"
            Property(name="status", data_type=DataType.TEXT, tokenization=field),      # current / superseded / accepted
            Property(name="effective_date", data_type=DataType.TEXT, tokenization=field),  # "YYYY-MM-DD" as text
            Property(name="section", data_type=DataType.TEXT, tokenization=word),      # heading path, searchable by words
            Property(name="source_file", data_type=DataType.TEXT, tokenization=field), # path, used for citations
            Property(name="title", data_type=DataType.TEXT, tokenization=word),        # document title
        ],
    )
    print(f"Created collection '{COLLECTION_NAME}'")
    return client.collections.get(COLLECTION_NAME)               # a handle we use to insert and query


def to_properties(chunk: Chunk) -> dict:
    """Pick the fields Weaviate should store for one chunk."""
    m = chunk.metadata                           # short name for readability
    return {
        "text": chunk.text,                      # breadcrumb + chunk text
        "chunk_id": chunk.chunk_id,
        "doc_id": m["doc_id"],
        "version": m.get("version", ""),         # .get with a default so a missing value never crashes
        "status": m.get("status", "unknown"),
        "effective_date": m.get("effective_date") or "",  # "or ''" turns None into an empty string
        "section": m.get("section", ""),
        "source_file": m.get("source_file", ""),
        "title": m.get("title", ""),
    }


def embed_chunks(chunks: list[Chunk], embedder: OllamaEmbeddings) -> list[list[float]]:
    """Embed all chunk texts, a batch at a time, and return one vector per chunk (same order)."""
    vectors = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):         # 0, 32, 64, ... up to the number of chunks
        batch = chunks[start : start + EMBED_BATCH_SIZE]          # the next slice of up to 32 chunks
        vectors.extend(embedder.embed_documents([c.text for c in batch]))  # one Ollama call -> 32 vectors
        print(f"  embedded {min(start + EMBED_BATCH_SIZE, len(chunks))}/{len(chunks)}")  # progress line
    return vectors


def index_chunks(collection, chunks: list[Chunk], vectors: list[list[float]]) -> int:
    """Insert (or overwrite) every chunk with its vector. Returns the number of failures."""
    with collection.batch.fixed_size(batch_size=100) as batch:    # groups inserts into requests of 100 objects
        for chunk, vector in zip(chunks, vectors):                # walk chunks and their vectors together
            batch.add_object(
                properties=to_properties(chunk),                  # the stored fields
                vector=vector,                                    # the embedding we computed
                uuid=generate_uuid5(chunk.chunk_id),              # same chunk_id -> same UUID -> overwrite, not duplicate
            )
    failed = collection.batch.failed_objects                      # anything Weaviate rejected
    for f in failed[:5]:                                          # show the first few errors, not hundreds
        print(f"  FAILED {f.object_.properties.get('chunk_id')}: {f.message}")
    return len(failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed chunks and load them into Weaviate.")
    parser.add_argument("--recreate", action="store_true", help="drop and rebuild the collection")  # a simple on/off flag
    args = parser.parse_args()                                    # read the flags from the command line

    chunks = chunk_corpus(load_corpus())                          # Phase 1: load files, then chunk them
    print(f"Chunks to index: {len(chunks)}")

    embedder = get_embedder()
    t0 = time.perf_counter()                                      # start the stopwatch
    vectors = embed_chunks(chunks, embedder)
    t_embed = time.perf_counter() - t0                            # seconds spent embedding
    print(f"Embedded {len(vectors)} chunks in {t_embed:.1f}s (vector size {len(vectors[0])})")

    # "with" opens the connection and always closes it at the end, even if something crashes.
    with weaviate.connect_to_local() as client:                   # localhost:8080 (HTTP) and 50051 (gRPC)
        collection = ensure_collection(client, recreate=args.recreate)
        t0 = time.perf_counter()
        n_failed = index_chunks(collection, chunks, vectors)
        print(f"Inserted in {time.perf_counter() - t0:.1f}s, failed: {n_failed}")

        total = collection.aggregate.over_all(total_count=True).total_count  # how many objects Weaviate now holds
        print(f"Objects in '{COLLECTION_NAME}': {total} (chunks: {len(chunks)})")
        if total != len(chunks) or n_failed:                      # counts must match exactly
            raise SystemExit("Mismatch: some chunks are missing or stale objects remain. Try --recreate.")
        print("OK: object count matches chunk count.")


if __name__ == "__main__":                                        # only runs when executed directly
    main()
