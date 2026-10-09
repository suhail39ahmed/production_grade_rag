#!/usr/bin/env bash
# ci_eval_gate.sh: runs the same commands as the "eval-gate" CI job, on a machine where Weaviate and Ollama
# are already running. Linux/macOS/Git Bash. Useful to reproduce a CI failure locally.
# Usage (repo root):  bash scripts/ci_eval_gate.sh            (set PY="uv run python" to use uv)

set -euo pipefail                                # stop at the first error, like CI does
PY="${PY:-python}"                               # which python command to use
SUMMARY="${GITHUB_STEP_SUMMARY:-reports/step_summary.md}"   # in CI GitHub sets this; locally write a file
export RERANK_MODEL="${RERANK_MODEL:-cross-encoder/ms-marco-MiniLM-L-6-v2}"

step() { echo; echo "=== $1  ($(date +%T))"; }   # a small helper that prints a step header with the time

step "Wait for Weaviate"
curl -sf http://localhost:8080/v1/.well-known/ready && echo "Weaviate ready"

step "Index the documents"
time $PY -m src.ingest.indexer --recreate

step "Retrieval-only evaluation"
time $PY -m src.eval.run_eval --retrieval-only

step "Quality gate (retrieval metrics)"
gate_status=0
$PY -m src.eval.check_gate --only retrieval || gate_status=$?   # remember the result, keep going

step "Write job summary -> $SUMMARY"
mkdir -p "$(dirname "$SUMMARY")"
$PY -m src.eval.summary_md --only retrieval --title "Retrieval gate" >> "$SUMMARY"

exit "$gate_status"                              # same exit code as the gate
