# check_gate.py: the CI quality gate. Compares reports/latest.json with eval/thresholds.yaml
# and exits with code 1 (= CI job fails) if any metric is below its minimum or above its maximum.
# Run from the repo root:  python -m src.eval.check_gate   (options: --report path --thresholds path --strict)

import argparse                                  # command-line flags
import json                                      # read the report
import sys                                       # sys.exit sets the exit code CI looks at
from pathlib import Path                         # file paths

import yaml                                      # read the thresholds file (pip install pyyaml)


def check(summary: dict, thresholds: dict, strict: bool = False) -> list[str]:
    """Return a list of failure messages (empty list = gate passed). Prints one line per rule."""
    failures = []
    for metric, rule in thresholds.items():      # e.g. "hit_at_5", {"min": 0.9}
        value = summary.get(metric)
        if value is None:                        # not measured in this run (e.g. ragas off, retrieval-only)
            print(f"  SKIP {metric:<26} not in report")
            if strict:
                failures.append(f"{metric} missing from the report")
            continue
        ok = True
        if "min" in rule and value < rule["min"]:
            ok = False
            failures.append(f"{metric} = {value} is below the minimum {rule['min']}")
        if "max" in rule and value > rule["max"]:
            ok = False
            failures.append(f"{metric} = {value} is above the maximum {rule['max']}")
        limits = " ".join(f"{k} {v}" for k, v in rule.items())  # e.g. "min 0.9"
        print(f"  {'PASS' if ok else 'FAIL'} {metric:<26} {value:<7} ({limits})")
    return failures


def main() -> None:
    p = argparse.ArgumentParser(description="Fail if evaluation metrics are below the thresholds.")
    p.add_argument("--report", default="reports/latest.json")
    p.add_argument("--thresholds", default="eval/thresholds.yaml")
    p.add_argument("--strict", action="store_true", help="also fail when a metric is missing from the report")
    args = p.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    thresholds = yaml.safe_load(Path(args.thresholds).read_text(encoding="utf-8"))  # safe_load = no code execution
    run = report["run"]
    print(f"Gate check: {args.report} (mode={run['mode']}, {run['n_questions']} questions, {run['timestamp']})")
    failures = check(report["summary"], thresholds, args.strict)
    if failures:
        print("\nGATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)                              # non-zero exit code -> CI marks the job as failed
    print("\nGATE PASSED")                       # exit code 0


if __name__ == "__main__":
    main()
