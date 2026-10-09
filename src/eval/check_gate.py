# check_gate.py: the CI quality gate. Compares reports/latest.json with eval/thresholds.yaml
# and exits with code 1 (= CI job fails) if any metric is below its minimum or above its maximum.
# Run from the repo root:
#   python -m src.eval.check_gate                                  # check every metric in the report
#   python -m src.eval.check_gate --only retrieval                 # just the retrieval metrics (CI fast gate)
#   python -m src.eval.check_gate --only unanswerable_refusal_acc,citation_valid
# Metrics named in --only MUST be in the report (missing = fail), so a gate can't silently pass on nothing.

import argparse                                  # command-line flags
import json                                      # read the report
import sys                                       # sys.exit sets the exit code CI looks at
from pathlib import Path                         # file paths

import yaml                                      # read the thresholds file (pip install pyyaml)

# Named groups you can pass to --only instead of typing every metric.
GROUPS = {
    "retrieval": ["hit_at_5", "recall_at_5", "recall_at_30", "section_hit_at_5", "mrr"],
    "generation": ["citation_valid", "unanswerable_refusal_acc", "wrong_refusal_rate",
                   "cited_correct_doc", "number_recall"],
}


def parse_only(only: str | None) -> list[str] | None:
    """'retrieval,faithfulness' -> ['hit_at_5', ..., 'mrr', 'faithfulness']; None -> None (= all)."""
    if not only:
        return None
    names = []
    for item in only.split(","):
        names.extend(GROUPS.get(item.strip(), [item.strip()]))  # a group expands; a plain name stays itself
    return names


def evaluate(summary: dict, thresholds: dict, only: list[str] | None = None, strict: bool = False) -> list[dict]:
    """Check every rule. Returns one row per metric: {metric, value, limits, status} with status
    PASS, FAIL or SKIP. A metric listed in `only` (or any metric with strict=True) that is missing -> FAIL."""
    rows = []
    for metric in only or thresholds:            # "or": the --only list if given, else every metric in the file
        if metric not in thresholds:
            rows.append({"metric": metric, "value": None, "limits": "no threshold defined",
                         "status": "FAIL"})      # a typo in --only should fail loudly, not be ignored
            continue
        rule = thresholds[metric]                # e.g. {"min": 0.95}
        limits = " ".join(f"{k} {v}" for k, v in rule.items())  # e.g. "min 0.95"
        value = summary.get(metric)
        if value is None:                        # not measured in this run
            status = "FAIL" if (only or strict) else "SKIP"
        elif ("min" in rule and value < rule["min"]) or ("max" in rule and value > rule["max"]):
            status = "FAIL"
        else:
            status = "PASS"
        rows.append({"metric": metric, "value": value, "limits": limits, "status": status})
    return rows


def failure_messages(rows: list[dict]) -> list[str]:
    """Readable one-line reasons for every FAIL row."""
    msgs = []
    for r in rows:
        if r["status"] != "FAIL":
            continue
        if r["value"] is None:
            msgs.append(f"{r['metric']}: missing from the report ({r['limits']})")
        else:
            msgs.append(f"{r['metric']} = {r['value']} does not meet {r['limits']}")
    return msgs


def load(report_path: str, thresholds_path: str) -> tuple[dict, dict]:
    """Read the report JSON and the thresholds YAML."""
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    thresholds = yaml.safe_load(Path(thresholds_path).read_text(encoding="utf-8"))  # safe_load = no code execution
    return report, thresholds


def main() -> None:
    p = argparse.ArgumentParser(description="Fail if evaluation metrics are below the thresholds.")
    p.add_argument("--report", default="reports/latest.json")
    p.add_argument("--thresholds", default="eval/thresholds.yaml")
    p.add_argument("--only", help="comma list of metrics or groups (retrieval, generation)")
    p.add_argument("--strict", action="store_true", help="also fail when a metric is missing from the report")
    args = p.parse_args()

    report, thresholds = load(args.report, args.thresholds)
    run = report["run"]
    print(f"Gate check: {args.report} (mode={run['mode']}, {run['n_questions']} questions, {run['timestamp']})")
    rows = evaluate(report["summary"], thresholds, parse_only(args.only), args.strict)
    for r in rows:
        value = "-" if r["value"] is None else r["value"]
        print(f"  {r['status']} {r['metric']:<26} {value!s:<7} ({r['limits']})")  # !s = format as text
    failures = failure_messages(rows)
    if failures:
        print("\nGATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)                              # non-zero exit code -> CI marks the job as failed
    print("\nGATE PASSED")                       # exit code 0


if __name__ == "__main__":
    main()
