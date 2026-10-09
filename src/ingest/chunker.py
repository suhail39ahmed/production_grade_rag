# chunker.py: splits each Document into small, labeled chunks ready for search.

import re                                   # regular expressions for spotting headings and divider lines
from dataclasses import dataclass, field    # simple data-holding classes

from langchain_text_splitters import (      # LangChain's text splitters (installed with langchain)
    MarkdownHeaderTextSplitter,             # splits text at #, ##, ### headings
    RecursiveCharacterTextSplitter,         # splits long text by size, trying nicer break points first
)

from src.ingest.loaders import HEADER_RE, Document, load_corpus  # reuse our loader pieces

CHUNK_SIZE = 800        # target max characters per chunk (tune this later with your eval set)
CHUNK_OVERLAP = 100     # characters repeated between pieces when a long paragraph must be cut


@dataclass
class Chunk:
    chunk_id: str                                  # unique ID that citations will point to
    text: str                                      # what gets embedded and searched
    metadata: dict = field(default_factory=dict)   # doc_id, version, status, section, etc.


def strip_header_block(text: str) -> str:
    """Remove the header lines (doc_id, version...) since they're already in metadata."""
    lines = text.splitlines()                      # work line by line
    head, body = lines[:40], lines[40:]            # the header only lives in the first 40 lines
    kept = []
    for line in head:
        if HEADER_RE.match(line):                  # a "Doc ID: ..." style line -> drop it
            continue
        if "FICTIONAL SAMPLE DATA" in line:        # the banner -> drop it
            continue
        if re.fullmatch(r"\s*[=\-]{5,}\s*", line): # divider lines like "=====" -> drop them
            continue
        kept.append(line)                          # everything else stays
    return "\n".join(kept + body)                  # put the text back together


def promote_caps_headings(text: str) -> str:
    """In .txt files, turn ALL-CAPS lines like '2. PERSONAL TRADING' into '## ' headings."""
    out = []
    for line in text.splitlines():
        s = line.strip()                               # ignore surrounding spaces
        letters = re.sub(r"[^A-Za-z]", "", s)          # keep only letters, to test if they're all caps
        if (letters and letters.isupper()              # has letters and they're all uppercase...
                and len(s) < 70                        # ...short enough to be a title...
                and not s.startswith(("-", "|", "#"))):  # ...and not a bullet, table row, or existing heading
            out.append("## " + s)                      # make it a Markdown heading
        else:
            out.append(line)                           # leave normal lines alone
    return "\n".join(out)


def split_blocks(text: str) -> list[str]:
    """Break a section into blocks: paragraphs, and whole tables (runs of lines starting with '|')."""
    blocks, current, in_table = [], [], False
    for line in text.splitlines():
        is_table_line = line.strip().startswith("|")   # table rows start with a pipe
        if is_table_line != in_table and current:      # switching between table and normal text...
            blocks.append("\n".join(current))          # ...closes the current block
            current = []
        in_table = is_table_line                       # remember which mode we're in
        if not line.strip() and not in_table:          # a blank line ends a paragraph
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)                           # add the line to the current block
    if current:                                        # don't forget the last block
        blocks.append("\n".join(current))
    return [b for b in blocks if b.strip()]            # drop empty blocks


def split_table(table: str, max_chars: int) -> list[str]:
    """Split a too-big table by rows, repeating the header row(s) on every piece."""
    rows = table.splitlines()
    has_separator = len(rows) > 1 and re.fullmatch(r"[\s|:\-]+", rows[1])  # Markdown's "|---|---|" line
    header = rows[:2] if has_separator else rows[:1]   # header = first row (+ separator line if present)
    pieces, current = [], list(header)
    for row in rows[len(header):]:                     # go through the data rows
        too_big = len("\n".join(current + [row])) > max_chars
        if too_big and len(current) > len(header):     # piece is full (and has at least one data row)...
            pieces.append("\n".join(current))          # ...save it
            current = list(header)                     # start a new piece with the header again
        current.append(row)
    pieces.append("\n".join(current))                  # save the last piece
    return pieces


# Used only for a single paragraph that's longer than CHUNK_SIZE on its own.
# It tries to cut at paragraph breaks, then line breaks, then sentences, then words.
_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def pack_section(section_text: str) -> list[str]:
    """Group a section's blocks into chunks of up to CHUNK_SIZE without cutting paragraphs or tables."""
    pieces, current = [], ""
    for block in split_blocks(section_text):
        is_table = block.lstrip().startswith("|")
        if len(block) > CHUNK_SIZE:                    # this one block is too big by itself
            if current:                                # first save whatever we've packed so far
                pieces.append(current)
                current = ""
            if is_table:
                pieces.extend(split_table(block, CHUNK_SIZE))   # big table -> split by rows
            else:
                pieces.extend(_text_splitter.split_text(block)) # big paragraph -> split with overlap
            continue
        candidate = f"{current}\n\n{block}" if current else block  # try adding this block
        if len(candidate) > CHUNK_SIZE:                # it would overflow...
            pieces.append(current)                     # ...so save the current chunk
            current = block                            # ...and start a new one with this block
        else:
            current = candidate                        # it fits, keep packing
    if current:                                        # save the last chunk
        pieces.append(current)
    return pieces


# Splits Markdown at headings and records which headings each piece sits under.
_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,                                # headings go into metadata, not the text
)


def chunk_document(doc: Document) -> list[Chunk]:
    """Turn one Document into a list of Chunks."""
    meta = doc.metadata
    body = strip_header_block(doc.text)                # remove header noise
    if meta["format"] == "txt":
        body = promote_caps_headings(body)             # make .txt headings look like Markdown

    chunks = []
    for section in _header_splitter.split_text(body):  # one item per heading section
        headings = [section.metadata[h] for h in ("h1", "h2", "h3") if h in section.metadata]
        section_path = " > ".join(h for h in headings if h != meta.get("title"))  # e.g. "5. Medallion Layers > 5.1 Bronze"
        for piece in pack_section(section.page_content):  # size-limited pieces of this section
            if len(piece.strip()) < 40:                # skip tiny scraps with no real content
                continue
            idx = len(chunks)                          # running number within this document
            breadcrumb = " > ".join(x for x in (meta.get("title", ""), section_path) if x)
            chunks.append(
                Chunk(
                    chunk_id=f"{meta['doc_id']}::v{meta.get('version', '0')}::{idx:03d}",  # e.g. TECH-RB-001::v2.3::002
                    text=f"{breadcrumb}\n\n{piece}",   # breadcrumb on top gives the search context
                    metadata={
                        **meta,                        # copy all doc-level metadata
                        "section": section_path or "(intro)",  # where in the doc this chunk lives
                        "chunk_index": idx,
                    },
                )
            )
    return chunks


def chunk_corpus(docs: list[Document]) -> list[Chunk]:
    """Chunk every document and return one flat list."""
    return [c for d in docs for c in chunk_document(d)]


if __name__ == "__main__":
    chunks = chunk_corpus(load_corpus())               # load + chunk everything
    sizes = [len(c.text) for c in chunks]
    print(f"{len(chunks)} chunks | min {min(sizes)} | avg {sum(sizes)//len(sizes)} | max {max(sizes)} chars\n")
    for c in chunks:                                   # show one example chunk
        if "ERR-PIPE-4012" in c.text:
            print(c.chunk_id, "|", c.metadata["section"])
            print(c.text[:400], "\n---")
            break