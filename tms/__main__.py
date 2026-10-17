"""Run from the repository root: python -m tms demo."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from modules.release_gate.gate.workflow_policy import Policy
from tms.engine import SCENARIOS, STRICT_EXIT, _unique, evaluate_run, execute_synthetic, review_case


def main(argv=None):
    parser = argparse.ArgumentParser(description="TMS — synthetic Test Management System demo")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Execute assertions, synthetic reviews and gate; check expected outcomes")
    demo.add_argument("--scenario", choices=["all", *SCENARIOS], default="all")
    demo.add_argument("--output-dir", type=Path)
    run = commands.add_parser("run", help="Execute synthetic tests; leave reviews pending")
    run.add_argument("--scenario", choices=SCENARIOS, default="go")
    run.add_argument("--output-dir", type=Path, required=True)
    review = commands.add_parser("review", help="Record a local, unauthenticated demo review")
    review.add_argument("--run-dir", type=Path, required=True)
    review.add_argument("--case", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--decision", choices=["approved", "rejected"], required=True)
    review.add_argument("--note", required=True)
    gate = commands.add_parser("gate", help="Evaluate a persisted synthetic run")
    gate.add_argument("--run-dir", type=Path, required=True)
    gate.add_argument("--strict", action="store_true")
    gate.add_argument("--policy", type=Path, help="Numeric risk-policy overrides; impact rubric is versioned separately")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            root = args.output_dir or Path("reports") / f"tms-demo-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
            scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
            lines = ["# TMS synthetic demo verification", "", "Green means expected demo outcomes; not deployment approval.", "", "| Scenario | Before review | After synthetic review | Expected |", "| --- | --- | --- | --- |"]
            for scenario in scenarios:
                directory = root / scenario
                execute_synthetic(scenario, directory)
                before = evaluate_run(directory)
                for case_id in ("BASE-001", "TARGET-001"):
                    review_case(directory, case_id, "Synthetic demo reviewer", "approved", "Simulated review for public demo; not a human production sign-off.")
                after = evaluate_run(directory)
                if after["decision"] != SCENARIOS[scenario]:
                    raise ValueError(f"{scenario}: expected {SCENARIOS[scenario]}, got {after['decision']}")
                lines.append(f"| {scenario} | {before['decision']} | {after['decision']} | {SCENARIOS[scenario]} |")
                print(f"{scenario}: {before['decision']} -> {after['decision']} (strict exit {STRICT_EXIT[after['decision']]})")
            (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"Reports: {root.resolve()}")
            return 0
        if args.command == "run":
            execute_synthetic(args.scenario, args.output_dir)
            result = evaluate_run(args.output_dir)
        elif args.command == "review":
            review_case(args.run_dir, args.case, args.reviewer, args.decision, args.note)
            result = evaluate_run(args.run_dir)
        else:
            try:
                overrides = json.loads(args.policy.read_text(encoding="utf-8"), object_pairs_hook=_unique) if args.policy else {}
                policy = Policy(**overrides)
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                print(f"Invalid policy configuration: {exc}")
                return 4
            result = evaluate_run(args.run_dir, policy=policy)
        print(f"{result['decision']} | evidence={result['evidence']['status']} | risk={result['risk']['score']}")
        return STRICT_EXIT[result["decision"]] if getattr(args, "strict", False) else 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"TMS input/evidence unavailable: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
