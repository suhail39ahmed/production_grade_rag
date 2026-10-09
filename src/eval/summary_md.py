# summary_md.py: turns reports/latest.json + eval/thresholds.yaml into a Markdown table with PASS/FAIL.
# In GitHub Actions, append it to the job's summary page:
#   python -m src.eval.summary_md --only retrieval >> "$GITHUB_STEP_SUMMARY"
# Locally, just run it and read the Markdown in the terminal.

import argparse                                  # command-line flags

from src.eval.check_gate import evaluate, load, parse_only  # reuse the gate's exact logic

ICONS = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "SKIP": "⏭️ SKIP"}  # emoji make the summary easy to scan


def to_markdown(report: dict, thresholds: dict, only: list[str] | None = None, title: str = "RAG eval") -> str:
    """Build the Markdown text: a header line, the gate table, then per-type numbers."""
    run = report["run"]
    rows = evaluate(report["summary"], thresholds, only)
    passed = all(r["status"] != "FAIL" for r in rows)       # all() = True if no row failed
    lines = [
        f"## {title}: {'✅ gate passed' if passed else '❌ gate FAILED'}",
        "",
        f"mode `{run['mode']}` · {run['n_questions']} questions · alpha {run['alpha']} · "
        f"reranker `{run['rerank_model']}` · LLM `{run['chat_model'] or '-'}` · {run['elapsed_seconds']}s",
        "",
        "| Metric | Value | Threshold | Result |",       # Markdown table header
        "|---|---:|---|---|",                             # ---: = right-align the numbers
    ]
    for r in rows:
        value = "-" if r["value"] is None else f"{r['value']:.3f}"
        lines.append(f"| `{r['metric']}` | {value} | {r['limits']} | {ICONS[r['status']]} |")

    keys = [r["metric"] for r in rows]                       # same metrics, broken down by question type
    lines += ["", "<details><summary>By question type</summary>", "",   # <details> = collapsible section
              "| Type | n | " + " | ".join(keys) + " |",
              "|---|---:|" + "---:|" * len(keys)]
    for t, s in report["by_type"].items():
        cells = ["-" if s.get(k) is None else f"{s[k]:.2f}" for k in keys]
        lines.append(f"| {t} | {s['n']} | " + " | ".join(cells) + " |")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Print the eval report as a Markdown table.")
    p.add_argument("--report", default="reports/latest.json")
    p.add_argument("--thresholds", default="eval/thresholds.yaml")
    p.add_argument("--only", help="same as check_gate --only, e.g. retrieval")
    p.add_argument("--title", default="RAG eval")
    args = p.parse_args()
    report, thresholds = load(args.report, args.thresholds)
    print(to_markdown(report, thresholds, parse_only(args.only), args.title))


if __name__ == "__main__":
    main()
