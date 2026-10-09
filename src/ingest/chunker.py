import re
from dataclasses import dataclass, field

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from src.ingest.loaders import HEADER_RE, Document, load_corpus

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict = field(default_factory=dict)


def strip_header_block(text: str) -> str:
    lines = text.splitlines()
    head, body = lines[:40], lines[40:]
    kept = []
    for line in head:
        if HEADER_RE.match(line):
            continue
        if "FICTIONAL SAMPLE DATA" in line:
            continue
        if re.fullmatch(r"\s*[=\-]{5,}\s*", line):
            continue
        kept.append(line)
    return "\n".join(kept + body)


def promote_caps_headings(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        letters = re.sub(r"[^A-Za-z]", "", s)
        if letters and letters.isupper() and len(s) < 70 and not s.startswith(("-", "|", "#")):
            out.append("## " + s)
        else:
            out.append(line)
    return "\n".join(out)


def split_blocks(text: str) -> list[str]:
    blocks, current, in_table = [], [], False
    for line in text.splitlines():
        is_table_line = line.strip().startswith("|")
        if is_table_line != in_table and current:
            blocks.append("\n".join(current))
            current = []
        in_table = is_table_line
        if not line.strip() and not in_table:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return [b for b in blocks if b.strip()]


def split_table(table: str, max_chars: int) -> list[str]:
    rows = table.splitlines()
    header = rows[:2] if len(rows) > 1 and re.fullmatch(r"[\s|:\-]+", rows[1]) else rows[:1]
    pieces, current = [], list(header)
    for row in rows[len(header):]:
        if len("\n".join(current + [row])) > max_chars and len(current) > len(header):
            pieces.append("\n".join(current))
            current = list(header)
        current.append(row)
    pieces.append("\n".join(current))
    return pieces


_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def pack_section(section_text: str) -> list[str]:
    pieces, current = [], ""
    for block in split_blocks(section_text):
        is_table = block.lstrip().startswith("|")
        if len(block) > CHUNK_SIZE:
            if current:
                pieces.append(current)
                current = ""
            if is_table:
                pieces.extend(split_table(block, CHUNK_SIZE))
            else:
                pieces.extend(_text_splitter.split_text(block))
            continue
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > CHUNK_SIZE:
            pieces.append(current)
            current = block
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,
)


def chunk_document(doc: Document) -> list[Chunk]:
    meta = doc.metadata
    body = strip_header_block(doc.text)
    if meta["format"] == "txt":
        body = promote_caps_headings(body)

    chunks = []
    for section in _header_splitter.split_text(body):
        headings = [section.metadata[h] for h in ("h1", "h2", "h3") if h in section.metadata]
        section_path = " > ".join(h for h in headings if h != meta.get("title"))
        for piece in pack_section(section.page_content):
            if len(piece.strip()) < 40:
                continue
            idx = len(chunks)
            breadcrumb = " > ".join(x for x in (meta.get("title", ""), section_path) if x)
            chunks.append(
                Chunk(
                    chunk_id=f"{meta['doc_id']}::v{meta.get('version', '0')}::{idx:03d}",
                    text=f"{breadcrumb}\n\n{piece}",
                    metadata={**meta, "section": section_path or "(intro)", "chunk_index": idx},
                )
            )
    return chunks


def chunk_corpus(docs: list[Document]) -> list[Chunk]:
    return [c for d in docs for c in chunk_document(d)]


if __name__ == "__main__":
    chunks = chunk_corpus(load_corpus())
    sizes = [len(c.text) for c in chunks]
    print(f"{len(chunks)} chunks | min {min(sizes)} | avg {sum(sizes)//len(sizes)} | max {max(sizes)} chars\n")
    for c in chunks:
        if "ERR-PIPE-4012" in c.text:
            print(c.chunk_id, "|", c.metadata["section"])
            print(c.text[:400], "\n---")
            break
