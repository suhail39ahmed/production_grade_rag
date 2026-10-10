# streamlit_app.py: a small web page for the RAG demo. It only talks to the FastAPI backend over HTTP.
# Start the API first (terminal 1):   uvicorn src.api.app:app
# Then this page (terminal 2):        streamlit run ui/streamlit_app.py      -> opens http://localhost:8501

import os                                        # environment variables
import re                                        # regular expressions (for [n] citations)

import requests                                  # simple HTTP client (installed with streamlit)
import streamlit as st                           # the UI framework: every widget is one function call

API_URL = os.getenv("API_URL", "http://localhost:8000")   # where the FastAPI backend runs

SAMPLES = {                                      # sidebar buttons: one per question type in the golden set
    "Exact lookup": "What does ERR-PIPE-4012 mean?",
    "Current limit": "What is the current equity VaR limit?",
    "Paraphrase": "How much can we lose before we have to cut risk?",
    "Multi-doc": "Could a company earning 15% of its revenue from thermal coal mining be held in the "
                 "Global Equity Fund? What about the Sustainable Infrastructure Fund?",
    "Old version": "What was the equity fund VaR limit before the April 2026 framework update?",
    "Unanswerable (trick)": "What is the expense ratio of the Halvorsen Ridge Emerging Markets Fund?",
}

st.set_page_config(page_title="RAG demo", page_icon="📚", layout="wide")  # must be the first st.* call


@st.cache_data(ttl=30)                           # remember the result for 30 s instead of calling every rerun
def get_health() -> dict:
    """Ask the API whether Weaviate and Ollama are up. Never raises."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        body = r.json()
        return body.get("detail", body) if r.status_code == 503 else body  # 503 puts details under "detail"
    except requests.RequestException as e:
        return {"status": "down", "error": str(e)}


def ask_api(question: str, alpha: float) -> dict:
    """POST the question; the answer can take a while on a CPU laptop, so allow up to 10 minutes."""
    r = requests.post(f"{API_URL}/ask", json={"question": question, "alpha": alpha}, timeout=600)
    if r.status_code != 200:                     # 422 = bad input, 503 = a service is down
        raise RuntimeError(f"API error {r.status_code}: {r.json().get('detail')}")
    return r.json()


def render_answer_text(text: str) -> str:
    """Make the answer safe and readable as Markdown."""
    text = text.replace("$", r"\$")              # "$" would otherwise start a math formula in Streamlit
    return re.sub(r"\[(\d+)\]", r" **[\1]**", text)  # make every [n] citation bold


def show_result(item: dict) -> None:
    """Draw one question + answer + sources."""
    st.markdown(f"#### ❓ {item['question']}")
    if item["refused"]:
        st.info(f"🙅 {item['answer']}  \nThe documents don't support an answer, so the system refuses "
                "instead of guessing.")
    else:
        st.markdown(render_answer_text(item["answer"]))
    for s in item["sources"]:                    # one collapsible box per cited source
        with st.expander(f"[{s['n']}] {s['doc_id']} · {s['section']}"):
            st.caption(f"`{s['chunk_id']}` · {s['source_file']}")
            st.markdown(s["text"].replace("$", r"\$"))  # chunks are Markdown (bold, tables): render them
    t = item["timings"]
    st.caption(" · ".join(f"{k} {v:.1f}s" for k, v in t.items())
               + f" · attempts {item['attempts']} · alpha {item['alpha']}")
    if item["check_errors"]:                     # the citation checker rejected a first attempt
        with st.expander("Citation check details"):
            for e in item["check_errors"]:
                st.write("•", e)
    st.divider()


# ---------- session state: survives the reruns Streamlit does after every click ----------
if "history" not in st.session_state:
    st.session_state.history = []                # list of answered questions, newest first
if "pending" not in st.session_state:
    st.session_state.pending = None              # a question waiting to be sent

# ---------- sidebar ----------
with st.sidebar:
    st.header("Try a question")
    for label, q in SAMPLES.items():
        if st.button(label, help=q, use_container_width=True):  # a click sets the question to run
            st.session_state.pending = q
    st.divider()
    alpha = st.slider("Hybrid alpha", 0.0, 1.0, 0.5, 0.05,
                      help="0 = keyword search only (BM25), 1 = vector search only")
    if st.button("Clear history"):
        st.session_state.history = []

# ---------- header with a health badge ----------
st.title("📚 Production-grade RAG demo")
health = get_health()
if health.get("status") == "ok":
    m = health["models"]
    st.success(f"Services OK · embed `{m['embed']}` · rerank `{m['rerank']}` · LLM `{m['chat']}`")
else:
    st.error(f"Backend not ready at {API_URL}: {health}")

with st.expander("How it works"):
    st.markdown(
        "1. **Hybrid search** in Weaviate (BM25 keywords + bge-m3 vectors) finds 30 candidate chunks, "
        "skipping superseded documents.\n"
        "2. A **cross-encoder reranker** keeps the best 5.\n"
        "3. **qwen2.5** answers using only those 5 sources and cites each sentence like [1].\n"
        "4. A **citation checker** (plain Python) rejects uncited sentences, fake source numbers and "
        "numbers that aren't in the cited source; the model gets one retry, then the system refuses.\n"
        "5. Questions the documents can't answer get *I don't know based on the documents.*"
    )

# ---------- question box ----------
with st.form("ask", clear_on_submit=True):       # a form only reruns the app when you press the button
    typed = st.text_input("Your question", placeholder="e.g. What does ERR-PIPE-4012 mean?")
    if st.form_submit_button("Ask") and typed.strip():
        st.session_state.pending = typed.strip()

# ---------- run the pending question ----------
if st.session_state.pending:
    question, st.session_state.pending = st.session_state.pending, None   # take it and clear it
    with st.spinner("Searching, reranking and writing a cited answer… (can take a minute on CPU)"):
        try:
            result = ask_api(question, alpha)
            result["alpha"] = alpha
            st.session_state.history.insert(0, result)                    # newest on top
        except Exception as e:
            st.error(str(e))

for item in st.session_state.history:
    show_result(item)
