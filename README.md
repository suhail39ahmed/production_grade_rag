# Production-grade RAG

Local RAG pipeline over sample investment + technology docs: load → chunk → embed into Weaviate → hybrid retrieve → cross-encoder rerank.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Docker Desktop](https://docs.docker.com/desktop/) (Weaviate)
- [Ollama](https://ollama.com/) with the embedding model pulled

```powershell
ollama pull bge-m3
```

## Setup

```powershell
uv sync
copy .env.example .env
docker compose up -d
```

## Index the corpus

```powershell
python -m src.ingest.indexer
# rebuild from scratch:
python -m src.ingest.indexer --recreate
```

## Search

```powershell
# hybrid search demo
python -m src.retrieval.search_demo
python -m src.retrieval.search_demo "What does ERR-PIPE-4012 mean?"

# hybrid vs rerank comparison
python -m src.retrieval.compare_demo
```

## Tests

```powershell
pytest -v
```

## Project layout

| Path | Role |
|------|------|
| `data/` | Sample corpus (md, txt, html, pdf) |
| `src/ingest/` | Loaders, chunker, Weaviate indexer |
| `src/retrieval/` | Hybrid retriever + demos |
| `src/rerank/` | Cross-encoder reranker |
| `eval/golden_qa.jsonl` | Eval questions |
| `docker-compose.yml` | Local Weaviate |
