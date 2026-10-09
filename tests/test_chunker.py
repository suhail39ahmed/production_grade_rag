# test_chunker.py: checks that chunking produces clean, citable chunks.
# Run from the repo root with:  pytest -v

import pytest                                              # the test runner

from src.ingest.chunker import CHUNK_SIZE, chunk_corpus, split_table
from src.ingest.loaders import load_corpus


@pytest.fixture(scope="module")      # a fixture = shared setup that tests can ask for by name
def chunks():                        # scope="module" = build it ONCE for this whole file, not once per test
    return chunk_corpus(load_corpus())  # load all 21 docs and chunk them


def test_chunks_were_created(chunks):         # pytest sees the "chunks" argument and passes in the fixture
    assert len(chunks) > 100                  # sanity check: we expect about 245, so fewer than 100 means something broke


def test_every_chunk_has_required_metadata(chunks):
    for c in chunks:
        for key in ("doc_id", "version", "status", "source_file", "section"):
            assert c.metadata.get(key), f"{c.chunk_id} is missing {key}"  # the message after the comma shows on failure


def test_no_chunk_is_too_long(chunks):
    limit = CHUNK_SIZE + 200                  # allow room for the breadcrumb and big table pieces
    too_long = [c.chunk_id for c in chunks if len(c.text) > limit]
    assert not too_long, f"Chunks over {limit} chars: {too_long}"  # lists exactly which chunks are too long


def test_no_chunk_is_empty(chunks):
    for c in chunks:
        assert len(c.text.strip()) >= 40, f"{c.chunk_id} is nearly empty"


def test_chunk_ids_are_unique(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"  # a set removes duplicates, so the sizes must match


def test_superseded_doc_is_marked(chunks):
    v1 = [c for c in chunks
          if c.metadata["doc_id"] == "INV-RMF-001" and c.metadata["version"] == "1.0"]
    assert v1, "v1 risk framework chunks are missing"            # the old version must still be loaded...
    assert all(c.metadata["status"] == "superseded" for c in v1)  # ...but clearly flagged as superseded


def test_error_code_chunk_keeps_its_section(chunks):
    hits = [c for c in chunks
            if c.metadata["doc_id"] == "TECH-RB-001" and "ERR-PIPE-4012" in c.metadata["section"]]
    assert hits, "No runbook chunk sits under the ERR-PIPE-4012 section"  # proves heading-based splitting works


def test_big_table_split_repeats_header():    # a unit test: made-up input, no files needed
    table = "| Name | Value |\n|---|---|\n" + "\n".join(f"| row{i} | {i} |" for i in range(100))
    pieces = split_table(table, max_chars=200)  # force the table to split
    assert len(pieces) > 1                       # it really did split
    for p in pieces:
        assert p.startswith("| Name | Value |\n|---|---|")  # every piece keeps the header row