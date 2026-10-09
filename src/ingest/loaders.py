# loaders.py: reads every doc (md, txt, html, pdf) into one common shape: text + metadata.

import re                                   # regular expressions, used to parse the header block
from dataclasses import dataclass, field    # dataclass = a simple class that just holds data
from pathlib import Path                    # Path = a clean, cross-platform way to work with file paths

from bs4 import BeautifulSoup               # BeautifulSoup parses HTML so we can walk its tags
from pypdf import PdfReader                 # PdfReader pulls text out of PDF pages


@dataclass                                  # auto-generates __init__ and __repr__ for us
class Document:                             # the ONE shape every loader returns
    text: str                               # the full cleaned text of the document
    metadata: dict = field(default_factory=dict)  # doc_id, version, etc. (default_factory gives each doc its own new dict)


# Maps the label as written in the docs -> the key name we use in code.
HEADER_KEYS = {
    "Title": "title",
    "Doc ID": "doc_id",
    "Version": "version",
    "Effective date": "effective_date",
    "Owner": "owner",
    "Status": "status",
}

# One regex that matches a header line in all three styles:
#   "- **Doc ID:** TECH-RB-001"     (Markdown)
#   "Doc ID:         INV-FS-HRSI"   (plain text)
#   "| Doc ID | TECH-AZ-001 |"      (HTML table after we convert it)
HEADER_RE = re.compile(
    r"^[\s\-*|]*"         # start of line, then skip any spaces, dashes, stars, or pipes
    r"\**"                # optional ** (Markdown bold opening)
    r"(Title|Doc ID|Version|Effective date|Owner|Status)"  # group 1: the label we care about
    r"\**\s*"             # optional ** (bold closing) and spaces
    r"[:|]"               # the separator: a colon or a table pipe
    r"\s*\**\s*"          # spaces and an optional ** after the colon
    r"(.+?)"              # group 2: the value (lazy, so it stops before trailing junk)
    r"\s*\|?\s*$",        # optional trailing spaces and a closing pipe, then end of line
    re.MULTILINE,         # makes ^ and $ match at each line, not just the whole string
)


def parse_header(text: str) -> dict:
    """Pull title, doc_id, version, etc. from the top of a document."""
    head = "\n".join(text.splitlines()[:40])        # only look at the first 40 lines, so we never match body text
    meta = {}                                       # results go here
    for key, value in HEADER_RE.findall(head):      # findall returns (label, value) pairs for every matching line
        meta.setdefault(HEADER_KEYS[key], value.strip())  # setdefault keeps the FIRST match if a label appears twice
    return meta


def load_text(path: Path) -> str:
    """Markdown and .txt files are already plain text."""
    return path.read_text(encoding="utf-8")         # always set the encoding, or Windows may misread special characters


def load_html(path: Path) -> str:
    """Convert HTML into Markdown-style text, keeping headings, lists, and tables."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")  # parse the HTML into a tree of tags
    body = soup.body or soup                        # use <body> if it exists, otherwise the whole document
    lines = []                                      # we'll build the output one line at a time
    for el in body.find_all(["h1", "h2", "h3", "p", "li", "tr", "pre"]):  # walk the tags that hold content, in order
        if el.find_parent(["p", "li", "tr", "pre"]):  # skip tags nested inside another content tag...
            continue                                  # ...so their text isn't added twice
        if el.name in ("h1", "h2", "h3"):           # headings
            level = int(el.name[1])                 # "h2" -> 2
            lines.append("#" * level + " " + el.get_text(" ", strip=True))  # "h2" becomes "## Heading text"
        elif el.name == "tr":                       # a table row
            cells = [c.get_text(" ", strip=True) for c in el.find_all(["th", "td"])]  # text of each cell
            lines.append("| " + " | ".join(cells) + " |")  # becomes "| cell1 | cell2 |" (a Markdown table row)
        elif el.name == "li":                       # a list item
            lines.append("- " + el.get_text(" ", strip=True))  # becomes a Markdown bullet
        else:                                       # paragraphs and <pre> blocks
            lines.append(el.get_text(" ", strip=True))  # plain text; " " joins inline tags with a space
    return "\n".join(lines)                         # one string, one line per element


def load_pdf(path: Path) -> str:
    """Extract text from every page of a PDF."""
    reader = PdfReader(path)                        # open the PDF
    return "\n\n".join(                             # blank line between pages
        page.extract_text() or ""                   # "or ''" handles pages with no text layer (scanned images)
        for page in reader.pages
    )


# Lookup table: file extension -> the function that loads it.
# Supporting a new format later is one new function + one new line here.
LOADERS = {
    ".md": load_text,
    ".txt": load_text,
    ".html": load_html,
    ".pdf": load_pdf,
}


def load_document(path: Path) -> Document:
    """Load one file into a Document, with metadata parsed from its header."""
    loader = LOADERS.get(path.suffix.lower())       # pick the loader by extension (.lower() so ".MD" works too)
    if loader is None:                              # unknown file type...
        raise ValueError(f"Unsupported file type: {path}")  # ...fail loudly rather than skip it silently
    text = loader(path)                             # run the right loader -> plain text
    meta = parse_header(text)                       # read doc_id, version, etc. from the header
        # --- clean up status: keep just the first word, lowercased ---
    raw_status = meta.get("status", "")                   # e.g. "SUPERSEDED — replaced by..."
    meta["status"] = raw_status.split()[0].lower() if raw_status else "unknown"  # -> "superseded"

    # --- clean up effective_date: keep only the first YYYY-MM-DD ---
    match = re.search(r"\d{4}-\d{2}-\d{2}", meta.get("effective_date", ""))  # find the first date pattern
    meta["effective_date"] = match.group(0) if match else None  # -> "2026-07-15", or None if there's no date
    if "doc_id" not in meta:                        # a doc we can't identify can't be cited later...
        raise ValueError(f"No Doc ID found in the header of {path}")  # ...so stop at ingestion time
    meta["source_file"] = path.as_posix()           # remember where it came from, with forward slashes on every OS
    meta["format"] = path.suffix.lstrip(".").lower()  # ".html" -> "html"
    return Document(text=text, metadata=meta)


def load_corpus(root: str = "data") -> list[Document]:
    """Load every supported file under the data folder."""
    paths = sorted(                                 # sorted = same order every run (reproducible)
        p for p in Path(root).rglob("*")            # rglob("*") = every file in every subfolder
        if p.suffix.lower() in LOADERS              # keep only formats we know how to load
    )
    return [load_document(p) for p in paths]        # load each one


# Runs only when you execute this file directly (python -m src.ingest.loaders),
# not when another file imports it.
if __name__ == "__main__":
    docs = load_corpus()                            # load everything under data/
    print(f"Loaded {len(docs)} documents\n")        # expect 21
    for d in docs:                                  # one summary line per doc
        m = d.metadata
        print(
            f"{m['doc_id']:<16} "                   # :<16 = left-align, pad to 16 characters
            f"v{m.get('version', '?'):<5} "         # .get(..., '?') = show '?' if missing instead of crashing
            f"{m.get('status', '?'):<12} "
            f"{m['format']:<5} "
            f"{len(d.text.split()):>5} words"       # rough word count; :>5 = right-align
        )