## CI: automatic quality gate

Every pull request and every push to `main` runs `.github/workflows/rag-ci.yml` on GitHub's
Linux runners (4 vCPU, 16 GB RAM, no GPU).

| Job | When | What it does | Typical time |
|---|---|---|---|
| `unit-tests` | every PR / push | `uv sync --locked`, then `pytest` (chunker, citations, metrics, gate, reranker). No Weaviate or Ollama needed. | 2-3 min (1-2 min with warm caches) |
| `eval-gate` | after `unit-tests` passes | Starts Weaviate 1.27.27 as a service container, installs Ollama + `bge-m3`, indexes `data/`, runs `run_eval --retrieval-only` on all 40 golden questions, then `check_gate --only retrieval`. Writes a PASS/FAIL table to the run's summary page and uploads `reports/` as an artifact. | 6-10 min |
| `full-eval` | nightly 03:00 IST + "Run workflow" button | Same as `eval-gate`, plus the LLM (`qwen2.5:7b` by default) on a small subset (`unanswerable,conflict_version`, 10 questions). Gates on retrieval + refusal + citation metrics. | 15-30 min |

Why the PR gate checks retrieval only: answering 40 questions with qwen2.5:7b on a 4-vCPU runner takes
40+ minutes, so generation is checked nightly on a subset instead. Retrieval problems (a chunking or
alpha change that loses the right section) are the most common regressions and are caught on every PR.

### Run the same checks on your machine
```powershell
uv run pytest -v                                         # = unit-tests job
uv run python -m src.ingest.indexer --recreate           # = eval-gate job, needs Docker Weaviate + Ollama running
uv run python -m src.eval.run_eval --retrieval-only
uv run python -m src.eval.check_gate --only retrieval    # exit code 1 = the gate would fail in CI
uv run python -m src.eval.summary_md --only retrieval     # the Markdown table CI shows
```

### Make the gate block merges (branch protection)
1. Push the workflow and let it run once (GitHub only offers check names it has already seen).
2. Settings → Rules → Rulesets → New branch ruleset (or the older Settings → Branches → Add branch protection rule).
3. Target branch: `main`. Turn on **Require a pull request before merging**.
4. Turn on **Require status checks to pass**, then add `unit-tests` and `eval-gate`.
   Do **not** add `full-eval` (it is skipped on PRs, so it would never report).
5. Optional: **Require branches to be up to date before merging**.

### Changing thresholds
`eval/thresholds.yaml` holds the limits. Change them in the same PR as the code change that justifies it,
with the before/after numbers in the PR description, so reviewers see why the bar moved.

### Recommended `pyproject.toml` addition (CPU-only PyTorch)
Without this, `uv sync` on the Linux runner installs the CUDA build of torch (about 3 GB of `nvidia-*` wheels).
With it, both Windows and Linux get the small CPU wheel. Run `uv lock` after adding it and commit `uv.lock`.
```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cpu" }]
```
Also make sure `pyyaml`, `ragas`, `langchain-community==0.4.1` and `pytest` (dev group) are in `pyproject.toml`.

### `.gitignore` additions
```gitignore
# Python / uv
__pycache__/
*.pyc
.venv/
.pytest_cache/
# Local settings and secrets
.env
# Evaluation output (CI uploads these as artifacts instead)
reports/
# Local model caches if you point HF_HOME / OLLAMA_MODELS inside the repo
.hf/
.ollama/
# Weaviate data if docker-compose mounts it inside the repo
weaviate_data/
```
