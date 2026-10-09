# citations.py: checks an LLM answer's citations with plain Python (no AI, so it's fast and predictable).
# Rules checked:
#   1. every sentence has at least one citation like [1]
#   2. every cited number is a real source (1..number of sources)
#   3. cheap support check: every number in a sentence (e.g. 2.0%, 30, 4012) appears in a source it cites
#      (numbers the user wrote in the question are allowed, e.g. "Can I sell 45 days after buying?")

import re                                        # regular expressions
from dataclasses import dataclass, field         # simple data-holding classes

from src.generate.prompt import REFUSAL          # the exact refusal sentence

CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")   # matches [1] and also [1, 2] (models sometimes write that)
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")  # a bullet or list marker at the start of a line: "- ", "* ", "2. "
# A sentence ends at . ! or ?, plus any citations right after it, then a space, then a capital letter or digit.
# Requiring a capital next means "2.0%" and "e.g. for" are NOT treated as sentence ends.
SENTENCE_END_RE = re.compile(r"(?<=[.!?])((?:\s*\[[\d,\s]+\])*)\s+(?=[A-Z0-9\"(])")
NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")  # 4012, 1,000, 2.0 (commas and decimals allowed)


@dataclass
class CheckResult:
    passed: bool                                 # True if the answer may be shown to the user
    refused: bool = False                        # True if the answer is exactly the refusal sentence
    errors: list[str] = field(default_factory=list)  # human-readable problems (also sent back to the LLM)
    cited: list[int] = field(default_factory=list)   # which source numbers were cited, e.g. [1, 3]


def find_citations(text: str) -> list[int]:
    """Return every source number cited in the text, e.g. '... [1][3]' -> [1, 3]."""
    nums = []
    for group in CITE_RE.findall(text):          # each match is the inside of one [...], e.g. "1" or "1, 2"
        nums.extend(int(x) for x in group.split(","))  # "1, 2" -> [1, 2]
    return nums


def split_sentences(answer: str) -> list[str]:
    """Split an answer into sentences, keeping each sentence's trailing citations with it."""
    sentences = []
    for line in answer.splitlines():             # bullets and paragraphs live on separate lines
        line = BULLET_RE.sub("", line).strip()   # drop "- " / "1. " so bullets look like normal sentences
        if not line or line.endswith(":"):       # skip blank lines and lead-ins like "The actions are:"
            continue
        # Put a marker after each sentence end (keeping "[1]" that follows the full stop), then split on it.
        marked = SENTENCE_END_RE.sub(lambda m: m.group(1) + "\n", line)
        for part in marked.split("\n"):
            part = part.strip()
            if not part:
                continue
            if CITE_RE.sub("", part).strip() == "" and sentences:  # a line that is ONLY "[1][2]"...
                sentences[-1] += " " + part      # ...belongs to the previous sentence
            else:
                sentences.append(part)
    return [s for s in sentences if s.strip() != REFUSAL]  # the refusal sentence never needs a citation


def numbers_in(text: str) -> set[float]:
    """All numbers in a text as floats, so '2.0' equals '2' and '1,000' equals '1000'."""
    return {float(n.replace(",", "")) for n in NUMBER_RE.findall(text)}


def check_answer(answer: str, chunk_texts: list[str], question: str = "") -> CheckResult:
    """Check an answer against the n sources it was given (chunk_texts[0] is source [1])."""
    text = answer.strip()
    if text == REFUSAL:                          # an honest "I don't know" is a valid outcome
        return CheckResult(passed=True, refused=True)

    n_sources = len(chunk_texts)
    question_numbers = numbers_in(question)      # numbers the user gave us may be repeated freely
    errors, all_cited = [], []
    sentences = split_sentences(text)
    if not sentences:                            # empty answer
        return CheckResult(passed=False, errors=["The answer is empty."])

    for s in sentences:
        cited = find_citations(s)                # the source numbers this sentence cites
        all_cited.extend(cited)
        short = s if len(s) <= 80 else s[:77] + "..."  # keep error messages readable
        if not cited:                            # rule 1
            errors.append(f'Missing citation: "{short}"')
            continue
        bad = [n for n in cited if not 1 <= n <= n_sources]  # rule 2: chained comparison = "between 1 and n"
        if bad:
            errors.append(f"Citation {bad} does not exist (only [1]..[{n_sources}]): \"{short}\"")
            continue
        claim_numbers = numbers_in(CITE_RE.sub("", s))           # numbers in the sentence, minus the [n] markers
        source_numbers = set().union(*(numbers_in(chunk_texts[n - 1]) for n in cited))  # numbers in cited sources
        missing = sorted(claim_numbers - source_numbers - question_numbers)  # not in cited sources or question
        if missing:                                              # rule 3
            shown = ", ".join(f"{x:g}" for x in missing)         # :g prints 2.0 as "2" and 4012.0 as "4012"
            found_in = sorted({i for i, t in enumerate(chunk_texts, start=1)  # which sources DO contain them,
                               if numbers_in(t) & set(missing)})               # so the retry knows what to cite
            hint = f" (they appear in {found_in})" if found_in else " (they appear in no source)"
            errors.append(f'Number(s) {shown} not found in cited source(s) {sorted(set(cited))}{hint}: "{short}"')

    return CheckResult(passed=not errors, errors=errors, cited=sorted(set(all_cited)))
