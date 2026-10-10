# app.py: a small web API around the RAG pipeline, so a UI (or curl) can ask questions over HTTP.
# Run from the repo root:  uvicorn src.api.app:app --reload        then open http://localhost:8000/docs
# Endpoints:
#   GET  /health  -> are Weaviate and Ollama reachable, and which models are in use
#   POST /ask     -> {"question": "...", "alpha": 0.5} -> answer + numbered sources + timings

import logging                                   # prints startup/shutdown messages
import os                                        # environment variables
import threading                                 # a lock so only one question runs at a time
import time                                      # timing
from contextlib import asynccontextmanager       # builds the startup/shutdown ("lifespan") hook

import httpx                                     # small HTTP client, used to ping Ollama
from fastapi import Depends, FastAPI, HTTPException, Request  # the web framework
from fastapi.middleware.cors import CORSMiddleware            # lets a browser page on another port call us
from pydantic import BaseModel, Field, StringConstraints      # request/response validation
from typing import Annotated                     # attaches validation rules to a type

from src.generate.answer import CANDIDATES, CHAT_MODEL, OLLAMA_BASE_URL, TOP_N, generate, get_llm
from src.ingest.indexer import EMBED_MODEL       # embedding model name (for /health)
from src.rerank.reranker import RERANK_MODEL, get_model, rerank
from src.retrieval.retriever import Retriever

log = logging.getLogger("rag-api")               # our own named logger
SNIPPET_CHARS = 600                              # how much chunk text to send back per source


# ---------- the pipeline object: created ONCE at startup and shared by every request ----------

class Pipeline:
    """Holds the Weaviate connection, the LLM client and a lock. Everything slow is set up once."""

    def __init__(self):
        self.retriever = Retriever()             # opens the Weaviate connection (HTTP 8080 + gRPC 50051)
        self.llm = get_llm()                     # ChatOllama client (no network call yet)
        self.lock = threading.Lock()             # CPU-bound LLM: answering two questions at once only slows both

    def warm_up(self) -> None:
        """Load the models now, so the FIRST user doesn't wait for it."""
        get_model()                              # loads the reranker into memory (cached afterwards)
        self.retriever.embedder.embed_query("warm up")  # makes Ollama load bge-m3
        self.llm.invoke([("human", "Reply with OK.")])  # makes Ollama load the chat model

    def ask(self, question: str, alpha: float):
        """Run retrieve -> rerank -> generate. Returns (Answer, the 5 chunks, timings)."""
        with self.lock:                          # one question at a time; others wait here
            t0 = time.perf_counter()
            candidates = self.retriever.retrieve(question, k=CANDIDATES, alpha=alpha)
            t1 = time.perf_counter()
            chunks = rerank(question, candidates, top_n=TOP_N)
            t2 = time.perf_counter()
            answer = generate(question, chunks, self.llm)
        timings = {"retrieve": t1 - t0, "rerank": t2 - t1, **answer.timings}  # ** merges in {"generate": ...}
        return answer, chunks, timings

    def health(self) -> dict:
        """Check both services. Never raises: returns True/False per service."""
        try:
            weaviate_ok = self.retriever.client.is_ready()   # Weaviate's own readiness check
        except Exception:
            weaviate_ok = False
        try:
            tags = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3).json()  # lists downloaded models
            names = {m["name"] for m in tags.get("models", [])}
            ollama_ok = True
            missing = [m for m in (EMBED_MODEL, CHAT_MODEL)                    # "bge-m3" is "bge-m3:latest"
                       if m not in names and f"{m}:latest" not in names]
        except Exception:
            ollama_ok, missing = False, []
        return {"weaviate": weaviate_ok, "ollama": ollama_ok, "missing_models": missing}

    def close(self) -> None:
        self.retriever.close()                   # close the Weaviate connection


# ---------- startup and shutdown ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code before 'yield' runs at startup, code after it at shutdown."""
    app.state.pipeline, app.state.startup_error = None, None
    try:
        pipeline = Pipeline()
        t0 = time.perf_counter()
        pipeline.warm_up()
        log.warning("Pipeline ready, warm-up took %.1fs", time.perf_counter() - t0)  # warning = always printed
        app.state.pipeline = pipeline
    except Exception as e:                       # services down: start anyway so /health can say what's wrong
        app.state.startup_error = f"{type(e).__name__}: {e}"
        log.error("Pipeline failed to start: %s", app.state.startup_error)
    yield                                        # the app serves requests while we're paused here
    if app.state.pipeline:
        app.state.pipeline.close()


app = FastAPI(title="Production-grade RAG demo", version="1.0", lifespan=lifespan)

if os.getenv("CORS_ORIGINS"):                    # e.g. "http://localhost:3000" for a separate web frontend
    app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS").split(","),
                       allow_methods=["GET", "POST"], allow_headers=["*"])


def get_pipeline(request: Request) -> Pipeline:
    """Dependency: hands the shared pipeline to an endpoint (tests swap this for a fake)."""
    pipeline = request.app.state.pipeline
    if pipeline is None:                         # startup failed (e.g. Docker/Ollama not running)
        raise HTTPException(503, f"Pipeline not available: {request.app.state.startup_error}")
    return pipeline


# ---------- request and response shapes (FastAPI validates these and shows them in /docs) ----------

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class AskRequest(BaseModel):
    question: Question                           # 3-500 characters after trimming spaces
    alpha: float = Field(0.5, ge=0.0, le=1.0)    # ge/le = "greater/less or equal": must be between 0 and 1
    model_config = {"json_schema_extra": {"examples": [   # the example shown in /docs
        {"question": "What does ERR-PIPE-4012 mean?", "alpha": 0.5}]}}


class SourceOut(BaseModel):
    n: int                                       # the [n] number used in the answer
    chunk_id: str
    doc_id: str
    section: str
    source_file: str
    text: str                                    # the start of the chunk text, so the UI can show it


class AskResponse(BaseModel):
    question: str
    answer: str
    refused: bool
    attempts: int
    sources: list[SourceOut]
    timings: dict[str, float]
    check_errors: list[str]


class HealthResponse(BaseModel):
    status: str                                  # "ok" or "degraded"
    weaviate: bool
    ollama: bool
    missing_models: list[str]
    models: dict[str, str]


# ---------- endpoints ----------
# They are plain "def" (not "async def"): FastAPI then runs them in a thread pool,
# so a slow, blocking LLM call doesn't freeze the whole server.

@app.get("/health", response_model=HealthResponse)
def health(pipeline: Pipeline = Depends(get_pipeline)):
    checks = pipeline.health()
    ok = checks["weaviate"] and checks["ollama"] and not checks["missing_models"]
    body = HealthResponse(
        status="ok" if ok else "degraded", **checks,
        models={"embed": EMBED_MODEL, "rerank": RERANK_MODEL, "chat": CHAT_MODEL},
    )
    if not ok:
        raise HTTPException(503, body.model_dump())  # 503 = "service unavailable", with the details
    return body


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, pipeline: Pipeline = Depends(get_pipeline)):
    try:
        answer, chunks, timings = pipeline.ask(req.question, req.alpha)
    except (httpx.HTTPError, ConnectionError, OSError) as e:   # Ollama/Weaviate unreachable mid-request
        raise HTTPException(503, f"A backend service is unavailable: {type(e).__name__}: {e}")
    sources = [
        SourceOut(n=s.n, chunk_id=s.chunk_id, doc_id=chunks[s.n - 1].doc_id, section=s.section,
                  source_file=s.source_file, text=chunks[s.n - 1].text[:SNIPPET_CHARS])
        for s in answer.sources                  # only the sources the answer cites
    ]
    return AskResponse(
        question=req.question, answer=answer.text, refused=answer.refused, attempts=answer.attempts,
        sources=sources, timings={k: round(v, 2) for k, v in timings.items()},
        check_errors=answer.check_errors,
    )
