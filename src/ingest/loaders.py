import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


HEADER_KEYS = {
    "Title": "title",
    "Doc ID": "doc_id",
    "Version": "version",
    "Effective date": "effective_date",
    "Owner": "owner",
    "Status": "status",
}
HEADER_RE = re.compile(
    r"^[\s\-*|]*\**(Title|Doc ID|Version|Effective date|Owner|Status)\**\s*[:|]\s*\**\s*(.+?)\s*\|?\s*$",
    re.MULTILINE,
)


def parse_header(text: str) -> dict:
    head = "\n".join(text.splitlines()[:40])
    meta = {}
    for key, value in HEADER_RE.findall(head):
        meta.setdefault(HEADER_KEYS[key], value.strip())
    return meta


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_html(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    body = soup.body or soup
    lines = []
    for el in body.find_all(["h1", "h2", "h3", "p", "li", "tr", "pre"]):
        if el.find_parent(["p", "li", "tr", "pre"]):
            continue
        if el.name in ("h1", "h2", "h3"):
            lines.append("#" * int(el.name[1]) + " " + el.get_text(" ", strip=True))
        elif el.name == "tr":
            cells = [c.get_text(" ", strip=True) for c in el.find_all(["th", "td"])]
            lines.append("| " + " | ".join(cells) + " |")
        elif el.name == "li":
            lines.append("- " + el.get_text(" ", strip=True))
        else:
            lines.append(el.get_text(" ", strip=True))
    return "\n".join(lines)


def load_pdf(path: Path) -> str:
    reader = PdfReader(path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


LOADERS = {".md": load_text, ".txt": load_text, ".html": load_html, ".pdf": load_pdf}


def load_document(path: Path) -> Document:
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type: {path}")
    text = loader(path)
    meta = parse_header(text)
    raw_status = meta.get("status", "")
    meta["status"] = raw_status.split()[0].lower() if raw_status else "unknown"
    match = re.search(r"\d{4}-\d{2}-\d{2}", meta.get("effective_date", ""))
    meta["effective_date"] = match.group(0) if match else None
    if "doc_id" not in meta:
        raise ValueError(f"No Doc ID found in the header of {path}")
    meta["source_file"] = path.as_posix()
    meta["format"] = path.suffix.lstrip(".").lower()
    return Document(text=text, metadata=meta)


def load_corpus(root: str = "data") -> list[Document]:
    paths = sorted(p for p in Path(root).rglob("*") if p.suffix.lower() in LOADERS)
    return [load_document(p) for p in paths]


if __name__ == "__main__":
    docs = load_corpus()
    print(f"Loaded {len(docs)} documents\n")
    for d in docs:
        m = d.metadata
        print(f"{m['doc_id']:<16} v{m.get('version', '?'):<5} {m.get('status', '?'):<12} {m['format']:<5} {len(d.text.split()):>5} words")
