"""Offline, synthetic-only entry point. Legacy run_gate.py remains unchanged."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gate.workflow_policy import Policy, evaluate_workflow, parse_time


STRICT_EXIT = {"GO": 0, "NO_GO": 1, "EVIDENCE_INSUFFICIENT": 2, "CONDITIONAL_GO": 3}


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def read_json(raw):
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def render_report(result):
    def safe(value):
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    score = result["risk"]["score"]
    lines = ["# Synthetic workflow release gate", "", "Proposed policy; advisory demo, not production release authorization.", "",
             f"- Policy: {result['policy_id']}", f"- Evaluated at: {result['evaluated_at']}",
             f"- Input SHA-256: {result['input_sha256']}", f"- Decision: **{result['decision']}**",
             f"- Evidence: {result['evidence']['status']}", f"- Release risk: {result['risk']['status']}",
             f"- Risk score: {score if score is not None else 'not assessed (never zero by default)'}", ""]
    for title, entries in [("Evidence gaps", result["evidence"]["issues"]), ("Release blockers", result["risk"]["blockers"])]:
        lines += [f"## {title}", ""] + [f"- {safe(entry)}" for entry in entries or ["None"]] + [""]
    lines += ["## Risk contributions", ""]
    lines += [f"- {safe(item['reason'])}: +{item['points']}" for item in result["risk"]["contributions"]] or ["- Not scored or no contributions."]
    lines += ["", "## Conditional acceptance", ""]
    lines += [f"- {safe(c['approved_by'])}: {safe(c['mitigation'])}; expires {safe(c['expires_at'])}" for c in result["conditions"]] or ["- None"]
    lines += ["", "## Resolved policy", "", "```json", json.dumps(result["policy"], indent=2), "```", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="synthetic workflow evidence JSON")
    parser.add_argument("--policy", type=Path, help="JSON object overriding proposed policy defaults")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/workflow"))
    parser.add_argument("--as-of", help="timezone-aware fixed evaluation time for reproducible demos only")
    parser.add_argument("--strict", action="store_true", help="0=GO, 1=NO_GO, 2=insufficient evidence, 3=conditional/manual hold")
    args = parser.parse_args(argv)
    try:
        overrides = read_json(args.policy.read_bytes()) if args.policy else {}
        if not isinstance(overrides, dict):
            raise ValueError("policy must be an object")
        policy = Policy(**overrides)
        now = parse_time(args.as_of) if args.as_of else None
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
        print(f"Invalid policy/evaluation configuration: {exc}")
        return 4

    raw = b""
    try:
        raw = args.input.read_bytes()
        data = read_json(raw)
        result = evaluate_workflow(data, policy, now=now)
    except (OSError, UnicodeError, ValueError) as exc:
        result = evaluate_workflow(None, policy, now=now)
        result["evidence"]["issues"] = [f"input could not be read: {exc}"]
    result["input_sha256"] = hashlib.sha256(raw).hexdigest() if raw else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    print(f"{result['decision']} | evidence={result['evidence']['status']} | risk={result['risk']['score']}")
    return STRICT_EXIT[result["decision"]] if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
