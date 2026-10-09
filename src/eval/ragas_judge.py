# ragas_judge.py: optional LLM-as-judge "faithfulness" score using Ragas, with a local Ollama model as the judge.
# Faithfulness = share of the answer's claims that the retrieved chunks actually support (0..1).
# Kept in its own file so the (heavy) ragas import only happens when you pass --ragas.

import asyncio                                   # ragas metrics are async; asyncio.run() calls them from normal code
import os                                        # environment variables

from openai import AsyncOpenAI                   # OpenAI client library; Ollama speaks the same API on /v1
from ragas.llms import llm_factory               # wraps a client so ragas can use it as a judge
from ragas.metrics.collections import Faithfulness  # the modern (ragas 0.4) faithfulness metric

from src.generate.citations import CITE_RE       # to strip [1] markers before judging

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("CHAT_MODEL", "qwen2.5:7b"))  # judge defaults to the chat model


def make_faithfulness():
    """Build the metric once; reuse it for every question."""
    client = AsyncOpenAI(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama")  # api_key is required but ignored
    judge = llm_factory(JUDGE_MODEL, provider="openai", client=client, temperature=0)  # temperature 0 = repeatable
    return Faithfulness(llm=judge)


def faithfulness_score(metric, question: str, answer: str, contexts: list[str]) -> float | None:
    """Score one answer. Returns None if the judge fails (e.g. it returned broken JSON)."""
    try:
        result = asyncio.run(metric.ascore(               # run the async call and wait for it
            user_input=question,
            response=CITE_RE.sub("", answer),             # "[1]" markers only confuse the judge
            retrieved_contexts=contexts,                  # the 5 chunks the answer was written from
        ))
        return round(float(result.value), 3)
    except Exception as e:                                # one bad judge reply shouldn't stop a long run
        print(f"    ragas failed: {type(e).__name__}: {str(e)[:120]}")
        return None
