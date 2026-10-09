# test_citations.py: fast unit tests for the citation checker (no LLM, no Weaviate, no Ollama).
# Run from the repo root:  pytest -v tests/test_citations.py

from src.generate.citations import check_answer, split_sentences
from src.generate.prompt import REFUSAL

# Two tiny fake sources. SOURCES[0] is [1], SOURCES[1] is [2].
SOURCES = [
    "ERR-PIPE-4012 means schema drift was detected in Bronze ingestion. The job is paused.",
    "The 1-day 99% VaR limit for equity funds is 2.0% of NAV.",
]


def test_valid_answer_passes():
    answer = "ERR-PIPE-4012 means schema drift was detected [1]. The equity VaR limit is 2.0% of NAV [2]."
    result = check_answer(answer, SOURCES)
    assert result.passed, result.errors          # show the errors if it fails
    assert result.cited == [1, 2]


def test_missing_citation_fails():
    result = check_answer("ERR-PIPE-4012 means schema drift [1]. The job is paused.", SOURCES)
    assert not result.passed
    assert "Missing citation" in result.errors[0]


def test_out_of_range_citation_fails():
    result = check_answer("The equity VaR limit is 2.0% of NAV [7].", SOURCES)
    assert not result.passed
    assert "does not exist" in result.errors[0]


def test_number_not_in_cited_source_fails():
    result = check_answer("The equity VaR limit is 3.5% of NAV [2].", SOURCES)  # 3.5 is made up
    assert not result.passed
    assert "3.5" in result.errors[0]


def test_number_cited_to_wrong_source_fails():
    result = check_answer("The equity VaR limit is 2.0% of NAV [1].", SOURCES)  # true, but [1] doesn't say it
    assert not result.passed
    assert "they appear in [2]" in result.errors[0]  # the error tells the LLM which source to cite instead


def test_number_from_the_question_is_allowed():
    question = "Is a 3.5% VaR allowed?"          # the user brought up 3.5 themselves
    result = check_answer("No, 3.5% is above the 2.0% of NAV limit [2].", SOURCES, question)
    assert result.passed, result.errors


def test_refusal_passes():
    result = check_answer(REFUSAL, SOURCES)
    assert result.passed and result.refused


def test_bullets_and_citation_after_full_stop():
    answer = "Actions:\n- Pause the job. [1]\n- Check the VaR limit of 2.0% [2]."
    assert split_sentences(answer) == ["Pause the job. [1]", "Check the VaR limit of 2.0% [2]."]
    assert check_answer(answer, SOURCES).passed


def test_decimal_and_abbreviation_do_not_split():
    sentences = split_sentences("The limit is 2.0% of NAV, e.g. for equity funds [2].")
    assert sentences == ["The limit is 2.0% of NAV, e.g. for equity funds [2]."]
