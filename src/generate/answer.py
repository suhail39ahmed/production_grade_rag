# answer.py: the full RAG pipeline: retrieve -> rerank -> generate -> check citations -> (retry) -> answer.
# generate() is separate from answer() so the evaluation can reuse the chunks it already retrieved.
# Run from the repo root:  python -m src.generate.answer "What does ERR-PIPE-4012 mean?"

import os                                        # reads environment variables (settings)
import sys                                       # command-line arguments
import time                                      # timing each step
from dataclasses import dataclass, field         # simple data-holding classes

from dotenv import load_dotenv                   # loads settings from .env
from langchain_ollama import ChatOllama          # LangChain wrapper for chat models served by Ollama

from src.generate.citations import check_answer  # our no-AI citation checker
from src.generate.prompt import REFUSAL, build_messages  # the prompt builder and the refusal sentence
from src.rerank.reranker import rerank           # Phase 3 reranker
from src.retrieval.retriever import Retriever    # Phase 3 hybrid retriever

load_dotenv()                                    # read .env so os.getenv sees its values

CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:7b")                         # which LLM to use
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")  # where Ollama listens
CANDIDATES = 30                                  # hybrid results handed to the reranker
TOP_N = 5                                        # reranked chunks the LLM actually sees
MAX_ATTEMPTS = 2                                 # first try + one retry with feedback


@dataclass
class Source:
    n: int                                       # the number used in the answer, e.g. 1 for [1]
    chunk_id: str                                # e.g. TECH-RB-001::v2.3::002
    section: str                                 # heading path inside the document
    source_file: str                             # file the chunk came from


@dataclass
class Answer:
    text: str                                    # the final answer shown to the user
    sources: list[Source]                        # only the sources the answer actually cites
    refused: bool                                # True if we answered with the refusal sentence
    attempts: int                                # how many times we called the LLM
    check_errors: list[str] = field(default_factory=list)  # problems found by the checker (all attempts)
    timings: dict = field(default_factory=dict)  # seconds spent in each step
    fallback: bool = False                       # True if we refused only because every attempt failed the check


def get_llm() -> ChatOllama:
    """The chat model. temperature=0 = always pick the most likely word, so answers are repeatable."""
    return ChatOllama(
        model=CHAT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,                           # no randomness
        num_ctx=8192,                            # context window in tokens; too small and Ollama silently cuts the prompt
    )


def generate(question: str, chunks, llm: ChatOllama) -> Answer:
    """Steps 3-4: ask the LLM using the given chunks, check citations, retry once, else refuse."""
    chunk_texts = [c.text for c in chunks]                        # chunk_texts[0] is source [1]
    feedback, all_errors = None, []
    t0 = time.perf_counter()
    for attempt in range(1, MAX_ATTEMPTS + 1):                    # attempt = 1, then 2
        messages = build_messages(question, chunks, feedback)    # feedback is None on the first try
        text = llm.invoke(messages).content.strip()               # step 3: ask the LLM
        result = check_answer(text, chunk_texts, question)        # step 4: check every citation
        if result.passed:                                         # good answer (or an honest refusal): done
            sources = [                                           # keep only the sources it actually cited
                Source(n, chunks[n - 1].chunk_id, chunks[n - 1].section, chunks[n - 1].source_file)
                for n in result.cited
            ]
            return Answer(text, sources, result.refused, attempt, all_errors,
                          {"generate": time.perf_counter() - t0})
        all_errors += [f"attempt {attempt}: {e}" for e in result.errors]  # remember what went wrong
        feedback = "\n".join(f"- {e}" for e in result.errors)    # tell the LLM what to fix next time

    return Answer(REFUSAL, [], True, MAX_ATTEMPTS, all_errors,    # still failing: refuse safely
                  {"generate": time.perf_counter() - t0}, fallback=True)


def answer(question: str, retriever: Retriever, llm: ChatOllama | None = None) -> Answer:
    """Answer one question with citations, or refuse if it can't be done safely."""
    llm = llm or get_llm()                       # "or" = use the given llm, else make one

    t0 = time.perf_counter()
    candidates = retriever.retrieve(question, k=CANDIDATES)       # step 1: broad hybrid search
    t_retrieve = time.perf_counter() - t0

    t0 = time.perf_counter()
    chunks = rerank(question, candidates, top_n=TOP_N)            # step 2: keep the best 5
    t_rerank = time.perf_counter() - t0

    result = generate(question, chunks, llm)                      # steps 3-4
    result.timings = {"retrieve": t_retrieve, "rerank": t_rerank, **result.timings}  # ** merges the dicts
    return result


def print_answer(a: Answer) -> None:
    """Print the answer, its sources, and how long each step took."""
    print(a.text)
    if a.sources:
        print("\nSources:")
        for s in a.sources:
            print(f"  [{s.n}] {s.chunk_id} | {s.section} | {s.source_file}")
    status = "refused" if a.refused else "answered"
    print(f"\n({status}, attempts: {a.attempts})")
    for e in a.check_errors:                     # show any rejected attempts, useful while learning
        print(f"  check error: {e}")
    print("Timings: " + ", ".join(f"{k} {v:.1f}s" for k, v in a.timings.items()))


def main() -> None:
    if len(sys.argv) < 2:                        # no question given
        raise SystemExit('Usage: python -m src.generate.answer "your question"')
    question = " ".join(sys.argv[1:])            # allows the question without quotes, too
    t0 = time.perf_counter()
    with Retriever() as retriever:               # one Weaviate connection, closed automatically
        a = answer(question, retriever)
    a.timings["total"] = time.perf_counter() - t0  # includes model loading on the first run
    print_answer(a)


if __name__ == "__main__":
    main()
