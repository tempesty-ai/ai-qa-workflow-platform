"""File-based TMS flow: real assertions against a synthetic in-memory product only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.release_gate.gate.workflow_policy import Policy, evaluate_workflow, parse_time
from tms.severity import GATE_LABEL, IMPACT_FIELDS, assess_severity

SCENARIOS = {"go": "GO", "conditional": "CONDITIONAL_GO", "no_go": "NO_GO", "insufficient": "EVIDENCE_INSUFFICIENT"}
STRICT_EXIT = {"GO": 0, "NO_GO": 1, "EVIDENCE_INSUFFICIENT": 2, "CONDITIONAL_GO": 3}
CATALOG = [
    {"case_id": "BASE-001", "suite": "baseline", "criticality": "critical",
     "name": "전체 알림 조회", "expected_count": 6},
    {"case_id": "TARGET-001", "suite": "target", "criticality": "high",
     "name": "경고 필터: 개수와 각 행의 심각도", "expected_count": 2},
]
NOTIFICATIONS = [{"id": f"SYNTHETIC-{i}", "level": level} for i, level in enumerate(
    ["info", "warning", "error", "info", "warning", "error"], 1)]


def utc_now():
    return datetime.now(timezone.utc)


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def snapshot_digest(run):
    snapshot = {k: v for k, v in run.items() if k != "reviews"}
    return digest_bytes(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"Duplicate JSON field: {k}")
        result[k] = v
    return result


def load_run(directory):
    run = json.loads((Path(directory) / "run.json").read_text(encoding="utf-8"), object_pairs_hook=_unique)
    if not isinstance(run, dict) or run.get("schema_version") != "tms-demo/v1" or run.get("synthetic") is not True:
        raise ValueError("Only a synthetic tms-demo/v1 run is supported")
    return run


def verify_artifacts(run, directory):
    issues = []
    directory = Path(directory).resolve()
    manifest = run.get("evidence_manifest")
    if not isinstance(manifest, list) or not manifest:
        return ["Evidence manifest missing"]
    seen_cases, seen_paths = set(), set()
    for item in manifest:
        if not isinstance(item, dict) or set(item) != {"case_id", "path", "sha256"}:
            issues.append("Malformed evidence manifest entry")
            continue
        case_id, relative = item["case_id"], item["path"]
        if not isinstance(case_id, str) or not isinstance(relative, str):
            issues.append("Invalid manifest identifier or path")
            continue
        path = (directory / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(directory):
            issues.append(f"{case_id}: evidence path outside run directory")
            continue
        if case_id in seen_cases or relative in seen_paths:
            issues.append(f"{case_id}: duplicate evidence entry")
        seen_cases.add(case_id)
        seen_paths.add(relative)
        try:
            if digest_bytes(path.read_bytes()) != item["sha256"]:
                issues.append(f"{case_id}: evidence digest mismatch")
        except OSError:
            issues.append(f"{case_id}: evidence file missing or unreadable")
    for result in run.get("results", []):
        if result.get("case_id") not in seen_cases or result.get("evidence_refs") != [
            m["path"] for m in manifest if isinstance(m, dict) and m.get("case_id") == result.get("case_id")
        ]:
            issues.append(f"{result.get('case_id')}: result/manifest mismatch")
    return issues


def execute_synthetic(scenario, directory, *, now=None):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown synthetic scenario")
    directory = Path(directory)
    if (directory / "run.json").exists():
        raise ValueError("Run already exists; choose a new output directory to preserve history")
    now = now or utc_now()
    run = {
        "schema_version": "tms-demo/v1", "synthetic": True, "scenario": scenario,
        "release": {"id": f"SYNTHETIC-TMS-{scenario}", "candidate_sha": "a" * 40, "environment": "synthetic-local"},
        "scope": [{k: c[k] for k in ("case_id", "suite", "criticality")} for c in CATALOG],
        "results": [], "defects": [], "evidence_manifest": [], "reviews": [],
        "readiness": {"qa_signoff": True, "operations_approval": True, "rollback_tested": True,
                      "monitoring_owner": "Synthetic demo owner", "rollback_trigger": "Synthetic smoke assertion failure"},
        "conditional_acceptance": {"approved_by": "Synthetic demo approver", "mitigation": "Use all-notifications view and inspect warning rows in the synthetic demo", "expires_at": (now + timedelta(hours=1)).isoformat()} if scenario == "conditional" else None,
    }
    for case in CATALOG:
        target = case["suite"] == "target"
        error = scenario == "insufficient" and target
        rows = [] if scenario == "no_go" and not target else [dict(row) for row in NOTIFICATIONS]
        if target and scenario != "conditional":
            rows = [r for r in rows if r["level"] == "warning"]
        count_ok = len(rows) == case["expected_count"]
        content_ok = not target or all(r["level"] == "warning" for r in rows)
        status = "error" if error else "passed" if count_ok and content_ok else "failed"
        # No PASS fixture is loaded: these assertions execute over actual synthetic rows.
        artifact = {"synthetic": True, "case": case, "candidate_sha": run["release"]["candidate_sha"],
                    "observed_at": now.isoformat(), "observed_rows": None if error else rows,
                    "assertions": [] if error else [{"name": "row_count", "passed": count_ok}, {"name": "row_content", "passed": content_ok}],
                    "error": "Injected synthetic environment unavailable" if error else None, "status": status}
        relative = f"evidence/{case['case_id']}.json"
        write_json(directory / relative, artifact)
        run["evidence_manifest"].append({"case_id": case["case_id"], "path": relative, "sha256": digest_bytes((directory / relative).read_bytes())})
        run["results"].append({"case_id": case["case_id"], "candidate_sha": run["release"]["candidate_sha"],
            "environment": run["release"]["environment"], "observed_at": now.isoformat(), "status": status,
            "failure_kind": "environment" if error else "none" if status == "passed" else "product",
            "flaky": False, "review": "pending", "evidence_refs": [relative]})
        if status == "failed":
            impact = {k: False for k in IMPACT_FIELDS}
            impact.update(core_journey_blocked=not target, major_function_impacted=True, workaround_verified=target)
            run["defects"].append({"id": f"SYNTHETIC-BUG-{case['case_id']}", "title": f"Synthetic {case['name']} failure",
                "status": "open", "priority": "normal", "impact": impact, "affected_scope": "all",
                "evidence_refs": [relative], "assessed_by": "Synthetic impact reviewer",
                "assessment_note": "Fault injection in a fictional notification product; no real incident."})
    write_json(directory / "run.json", run)
    return run


def review_case(directory, case_id, reviewer, decision, note, *, now=None):
    if decision not in ("approved", "rejected") or not reviewer.strip() or not note.strip():
        raise ValueError("A reviewer, explicit decision and review note are required")
    run = load_run(directory)
    issues = verify_artifacts(run, directory)
    if issues:
        raise ValueError("; ".join(issues))
    if case_id not in {r["case_id"] for r in run["results"]}:
        raise ValueError("Review case does not belong to this run")
    run["reviews"].append({"case_id": case_id, "reviewer": reviewer, "decision": decision, "note": note,
                           "reviewed_at": (now or utc_now()).isoformat(), "snapshot_sha256": snapshot_digest(run)})
    write_json(Path(directory) / "run.json", run)
    return run


def evaluate_run(directory, *, now=None, policy=None):
    now = now or utc_now()
    run = load_run(directory)
    issues = verify_artifacts(run, directory)
    digest = snapshot_digest(run)
    selected = {}
    observed_at = {r["case_id"]: parse_time(r["observed_at"]) for r in run["results"]}
    for review in run["reviews"]:
        if (review.get("snapshot_sha256") == digest and review.get("reviewer", "").strip()
                and review.get("note", "").strip() and review.get("decision") in ("approved", "rejected")):
            reviewed_at = parse_time(review["reviewed_at"])
            if review.get("case_id") in observed_at and observed_at[review["case_id"]] <= reviewed_at <= now + timedelta(minutes=5):
                selected[review["case_id"]] = review["decision"]
    results = [{**r, "review": selected.get(r["case_id"], "pending") if not issues else "pending"} for r in run["results"]]
    defects, assessments = [], []
    declared_refs = {m["path"] for m in run["evidence_manifest"] if isinstance(m, dict) and isinstance(m.get("path"), str)}
    for defect in run["defects"]:
        assessment = assess_severity(defect)
        assessments.append({"id": defect["id"], **assessment})
        if not set(defect.get("evidence_refs", [])).issubset(declared_refs):
            issues.append(f"{defect['id']}: impact evidence does not belong to this run")
        if assessment["severity"] == "UNCLASSIFIED":
            issues.append(f"{defect['id']}: impact classification incomplete")
        else:
            defects.append({"id": defect["id"], "severity": GATE_LABEL[assessment["severity"]], "status": defect["status"]})
    export = {"schema_version": 1, "synthetic": True, "release": run["release"], "scope": run["scope"],
              "results": results, "defects": defects, "readiness": run["readiness"], "conditional_acceptance": run["conditional_acceptance"]}
    result = evaluate_workflow(export, policy or Policy(), now=now)
    if issues:
        result["evidence"]["status"] = "INSUFFICIENT"
        result["evidence"]["issues"].extend(issues)
        if not (result["risk"]["score"] is None and result["risk"]["blockers"]):
            result["decision"] = "EVIDENCE_INSUFFICIENT"
            result["risk"] = {"status": "NOT_ASSESSED", "score": None, "blockers": [], "contributions": []}
    result["tms"] = {"run_snapshot_sha256": digest, "severity_assessments": assessments,
                     "review_count": len(run["reviews"]), "synthetic_approvals_only": True}
    write_json(Path(directory) / "gate-input.json", export)
    write_json(Path(directory) / "gate-result.json", result)
    write_report(directory, result)
    return result


def write_report(directory, result):
    score = result["risk"]["score"]
    lines = ["# TMS — Test Management System", "", "Synthetic demo; proposed policy; not production release authorization.", "",
             f"- Decision: **{result['decision']}**", f"- Evidence: {result['evidence']['status']}",
             f"- Risk score: {score if score is not None else 'not assessed'}", f"- Policy: {result['policy_id']}",
             f"- Evaluated at: {result['evaluated_at']}", f"- Run snapshot SHA-256: {result['tms']['run_snapshot_sha256']}",
             "", "## Impact classification", ""]
    lines += [f"- {a['id']}: {a['severity']} ({a['rule']}) — {a['reason']}" for a in result["tms"]["severity_assessments"]] or ["- No synthetic defects."]
    for title, entries in [("Evidence gaps", result["evidence"]["issues"]), ("Release blockers", result["risk"]["blockers"])]:
        lines += ["", f"## {title}", ""] + [f"- {str(v).replace(chr(10), ' ')}" for v in entries or ["None"]]
    lines += ["", "## Resolved risk policy", "", "```json", json.dumps(result["policy"], indent=2), "```", ""]
    (Path(directory) / "report.md").write_text("\n".join(lines), encoding="utf-8")
