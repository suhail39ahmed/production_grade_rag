import pytest

from src.ingest.chunker import CHUNK_SIZE, chunk_corpus, split_table
from src.ingest.loaders import load_corpus


@pytest.fixture(scope="module")
def chunks():
    return chunk_corpus(load_corpus())


def test_chunks_were_created(chunks):
    assert len(chunks) > 100


def test_every_chunk_has_required_metadata(chunks):
    for c in chunks:
        for key in ("doc_id", "version", "status", "source_file", "section"):
            assert c.metadata.get(key), f"{c.chunk_id} is missing {key}"


def test_no_chunk_is_too_long(chunks):
    limit = CHUNK_SIZE + 200
    too_long = [c.chunk_id for c in chunks if len(c.text) > limit]
    assert not too_long, f"Chunks over {limit} chars: {too_long}"


def test_no_chunk_is_empty(chunks):
    for c in chunks:
        assert len(c.text.strip()) >= 40, f"{c.chunk_id} is nearly empty"


def test_chunk_ids_are_unique(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"


def test_superseded_doc_is_marked(chunks):
    v1 = [c for c in chunks if c.metadata["doc_id"] == "INV-RMF-001" and c.metadata["version"] == "1.0"]
    assert v1, "v1 risk framework chunks are missing"
    assert all(c.metadata["status"] == "superseded" for c in v1)


def test_error_code_chunk_keeps_its_section(chunks):
    hits = [c for c in chunks if c.metadata["doc_id"] == "TECH-RB-001" and "ERR-PIPE-4012" in c.metadata["section"]]
    assert hits, "No runbook chunk sits under the ERR-PIPE-4012 section"


def test_big_table_split_repeats_header():
    table = "| Name | Value |\n|---|---|\n" + "\n".join(f"| row{i} | {i} |" for i in range(100))
    pieces = split_table(table, max_chars=200)
    assert len(pieces) > 1
    for p in pieces:
        assert p.startswith("| Name | Value |\n|---|---|")
