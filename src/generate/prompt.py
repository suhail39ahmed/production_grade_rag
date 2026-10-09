# prompt.py: builds the chat messages we send to the LLM: strict rules + numbered sources + the question.

REFUSAL = "I don't know based on the documents."   # the ONE exact sentence the model must use when it can't answer

SYSTEM_PROMPT = f"""You answer questions about internal company documents.

Rules:
1. Use ONLY the numbered sources below. Never use outside knowledge.
2. Put a citation like [1] at the end of EVERY sentence. Use [1][2] if a sentence uses two sources.
3. Only cite numbers that exist in the sources list.
4. Copy numbers, limits and codes exactly as written in the sources.
5. If the sources do not contain the answer, reply with exactly: {REFUSAL}
6. Be concise: at most 5 sentences. Plain sentences or "- " bullets only. No headings, no "Sources:" list."""
# f"..." lets us drop REFUSAL into the text, so the prompt and the checker always use the same string.


def format_sources(chunks) -> str:
    """Number the chunks [1]..[n], each with a small header saying where it came from."""
    blocks = []
    for n, c in enumerate(chunks, start=1):                     # n = 1, 2, 3... (humans count from 1)
        header = f"[{n}] {c.doc_id} v{c.version} | {c.section}"  # e.g. "[1] TECH-RB-001 v2.3 | 3. ERR-PIPE-4012 ..."
        blocks.append(f"{header}\n{c.text}")                    # header line, then the chunk text
    return "\n\n---\n\n".join(blocks)                           # a "---" line between sources keeps them apart


def build_messages(question: str, chunks, feedback: str | None = None) -> list[tuple[str, str]]:
    """Return [("system", rules), ("human", sources + question)], the format ChatOllama accepts."""
    user = f"Sources:\n\n{format_sources(chunks)}\n\nQuestion: {question}"  # sources first, question last
    if feedback:                                                # only on a retry
        user += (
            "\n\nYour previous answer was rejected for these reasons:\n"
            f"{feedback}\n"
            "Write the answer again and fix every problem. "
            f"If the sources cannot support an answer, reply exactly: {REFUSAL}"
        )
    return [("system", SYSTEM_PROMPT), ("human", user)]         # (role, text) pairs
