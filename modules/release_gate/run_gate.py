from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gate.data_loader import load_csv, load_json
from gate.release_gate import decide_gate
from gate.report_generator import write_report


ROOT = Path(__file__).resolve().parent


# Exit codes: 0 = release may proceed, 1 = NO_GO. Used by CI to block a merge.
EXIT_OK = 0
EXIT_NO_GO = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QA release gate")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when the gate returns NO_GO, so CI fails the build",
    )
    args = parser.parse_args(argv)

    release = load_json(ROOT / "data" / "release_sample.json")
    defects = load_csv(ROOT / "data" / "defects_sample.csv")
    test_results = load_csv(ROOT / "data" / "test_results_sample.csv")

    result = decide_gate(release, defects, test_results)
    output_path = write_report(result, release, ROOT / "reports" / "release_gate_report.md")

    print(f"Release Gate: {result.status}")
    print(f"Risk Score: {result.score}/100")
    print(f"Report: {output_path}")
    for risk in result.top_risks[:5]:
        print(f"  - {risk.reason} (+{risk.points})")

    if args.strict and result.status == "NO_GO":
        print("NO_GO: release blocked. See the report for the contributing items.")
        return EXIT_NO_GO
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

