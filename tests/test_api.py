# test_api.py: tests the FastAPI layer with a FAKE pipeline (no Weaviate, no Ollama, no models).
# Run from the repo root:  pytest -v tests/test_api.py

import pytest
from fastapi.testclient import TestClient        # calls the app in-process, like a real HTTP client

from src.api.app import app, get_pipeline
from src.generate.answer import Answer, Source
from src.retrieval.retriever import SearchResult


class FakePipeline:
    """Same methods as the real Pipeline, but returns canned data instantly."""

    def ask(self, question, alpha):
        chunk = SearchResult(chunk_id="TECH-RB-001::v2.3::002", text="ERR-PIPE-4012 means schema drift.",
                             doc_id="TECH-RB-001", version="2.3", section="3. ERR-PIPE-4012",
                             source_file="data/technology/incident_runbook_data_pipelines.md", score=0.9)
        answer = Answer(text="It means schema drift [1].", refused=False, attempts=1,
                        sources=[Source(1, chunk.chunk_id, chunk.section, chunk.source_file)],
                        timings={"generate": 1.234})
        return answer, [chunk], {"retrieve": 0.1, "rerank": 0.2, "generate": 1.234}

    def health(self):
        return {"weaviate": True, "ollama": True, "missing_models": []}


@pytest.fixture
def client():
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()   # swap the real pipeline for the fake
    yield TestClient(app)        # not "with TestClient(app)": that would run the real startup (lifespan)
    app.dependency_overrides.clear()


def test_ask_success_shape(client):
    r = client.post("/ask", json={"question": "What does ERR-PIPE-4012 mean?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "It means schema drift [1]." and body["refused"] is False
    assert body["sources"][0] == {
        "n": 1, "chunk_id": "TECH-RB-001::v2.3::002", "doc_id": "TECH-RB-001", "section": "3. ERR-PIPE-4012",
        "source_file": "data/technology/incident_runbook_data_pipelines.md",
        "text": "ERR-PIPE-4012 means schema drift.",
    }
    assert body["timings"]["generate"] == 1.23   # rounded to 2 decimals


@pytest.mark.parametrize("payload", [
    {"question": ""},                            # empty
    {"question": "   "},                         # only spaces (stripped -> empty)
    {"question": "x" * 501},                     # too long
    {"question": "Valid question?", "alpha": 1.5},  # alpha out of range
    {},                                          # missing question
])
def test_ask_validation_errors(client, payload):
    assert client.post("/ask", json=payload).status_code == 422   # 422 = "Unprocessable Entity" (bad input)


def test_health_shape(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["weaviate"] and body["ollama"]
    assert set(body["models"]) == {"embed", "rerank", "chat"}


def test_503_when_pipeline_missing():
    app.state.pipeline, app.state.startup_error = None, "ConnectionError: Weaviate down"  # as after a failed startup
    r = TestClient(app).post("/ask", json={"question": "What does ERR-PIPE-4012 mean?"})
    assert r.status_code == 503 and "Weaviate down" in r.json()["detail"]
