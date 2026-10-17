"""Proposed synthetic workflow policy; deliberately independent of the legacy gate."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
import re


POLICY_ID = "workflow-proposal-v1"


@dataclass(frozen=True)
class Policy:
    conditional_min: int = 20
    no_go_min: int = 45
    max_age_hours: float = 24
    future_tolerance_minutes: float = 5
    p2_points: int = 15
    p3_points: int = 5
    high_failure_points: int = 12
    medium_failure_points: int = 6
    low_failure_points: int = 3
    flaky_points: int = 5

    def __post_init__(self):
        values = asdict(self)
        for name, value in values.items():
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        for name in values.keys() - {"max_age_hours", "future_tolerance_minutes"}:
            if type(values[name]) is not int or values[name] < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not 0 < self.conditional_min < self.no_go_min <= 100:
            raise ValueError("require 0 < conditional_min < no_go_min <= 100")
        if not 0 < self.max_age_hours <= 8760 or not 0 <= self.future_tolerance_minutes <= 60:
            raise ValueError("age must be in (0, 8760] hours; future tolerance in [0, 60] minutes")


def parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _keys(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required.split()):
        raise ValueError(f"{label}: expected exactly {required}")


def validate_contract(data):
    """Reject malformed/ambiguous inputs rather than coercing them into a passing run."""
    _keys(data, "schema_version synthetic release scope results defects readiness conditional_acceptance", "input")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["synthetic"] is not True:
        raise ValueError("only schema_version=1 and synthetic=true are supported")
    release = data["release"]
    _keys(release, "id candidate_sha environment", "release")
    if not all(_text(v) for v in release.values()) or not re.fullmatch(r"[0-9a-f]{40}", release["candidate_sha"]):
        raise ValueError("release requires id, environment and a 40-character lowercase candidate SHA")
    for key in ("scope", "results", "defects"):
        if not isinstance(data[key], list):
            raise ValueError(f"{key} must be a list")
    ids = set()
    for case in data["scope"]:
        _keys(case, "case_id suite criticality", "scope item")
        if not _text(case["case_id"]) or case["case_id"] in ids:
            raise ValueError("scope case_id must be nonempty and unique")
        ids.add(case["case_id"])
        if case["suite"] not in ("baseline", "target") or case["criticality"] not in ("critical", "high", "medium", "low"):
            raise ValueError("invalid scope suite or criticality")
    seen = set()
    for run in data["results"]:
        _keys(run, "case_id candidate_sha environment observed_at status failure_kind flaky review evidence_refs", "result")
        if not _text(run["case_id"]) or run["case_id"] not in ids or run["case_id"] in seen:
            raise ValueError("results require unique, in-scope case_id; select one run per case explicitly")
        seen.add(run["case_id"])
        if not _text(run["candidate_sha"]) or not _text(run["environment"]):
            raise ValueError("result candidate_sha and environment must be nonempty strings")
        parse_time(run["observed_at"])
        if run["status"] not in ("passed", "failed", "blocked", "error", "not_run"):
            raise ValueError("invalid result status")
        if run["failure_kind"] not in ("none", "product", "automation", "environment", "unknown"):
            raise ValueError("invalid failure_kind")
        if run["status"] == "passed" and run["failure_kind"] != "none":
            raise ValueError("passed result requires failure_kind=none")
        if run["status"] != "passed" and run["failure_kind"] == "none":
            raise ValueError("non-passed result requires an explicit failure_kind")
        if type(run["flaky"]) is not bool or run["review"] not in ("approved", "pending", "rejected"):
            raise ValueError("invalid flaky boolean or review")
        refs = run["evidence_refs"]
        if not isinstance(refs, list) or not all(_text(ref) for ref in refs):
            raise ValueError("evidence_refs must be a list of nonempty opaque references")
    ids = set()
    for defect in data["defects"]:
        _keys(defect, "id severity status", "defect")
        if not _text(defect["id"]) or defect["id"] in ids:
            raise ValueError("defect ids must be nonempty and unique")
        ids.add(defect["id"])
        if defect["severity"] not in ("P1", "P2", "P3") or defect["status"] not in ("open", "resolved"):
            raise ValueError("invalid defect severity or status")
    readiness = data["readiness"]
    _keys(readiness, "qa_signoff operations_approval rollback_tested monitoring_owner rollback_trigger", "readiness")
    for key in ("qa_signoff", "operations_approval", "rollback_tested"):
        if type(readiness[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    for key in ("monitoring_owner", "rollback_trigger"):
        if not isinstance(readiness[key], str):
            raise ValueError(f"{key} must be a string")
    acceptance = data["conditional_acceptance"]
    if acceptance is not None:
        _keys(acceptance, "approved_by mitigation expires_at", "conditional_acceptance")
        if not isinstance(acceptance["approved_by"], str) or not isinstance(acceptance["mitigation"], str):
            raise ValueError("conditional acceptance owner and mitigation must be strings")
        parse_time(acceptance["expires_at"])


def classify_risk(score: int, conditional_required: bool, policy: Policy) -> str:
    if score >= policy.no_go_min:
        return "NO_GO"
    if conditional_required or score >= policy.conditional_min:
        return "CONDITIONAL_GO"
    return "GO"


def evaluate_workflow(data, policy: Policy | None = None, *, now: datetime | None = None) -> dict:
    policy = policy or Policy()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("evaluation time must include a timezone")
    now = now.astimezone(timezone.utc)
    result = {
        "policy_id": POLICY_ID, "policy": asdict(policy), "evaluated_at": now.isoformat(),
        "synthetic": None, "decision": "EVIDENCE_INSUFFICIENT",
        "evidence": {"status": "INSUFFICIENT", "issues": []},
        "risk": {"status": "NOT_ASSESSED", "score": None, "blockers": [], "contributions": []},
        "conditions": [],
    }
    try:
        validate_contract(data)
    except (ValueError, TypeError, KeyError) as exc:
        result["evidence"]["issues"].append(f"contract: {exc}")
        return result

    result["synthetic"] = True
    result["release"] = data["release"].copy()
    issues = result["evidence"]["issues"]
    blockers = result["risk"]["blockers"]
    runs = {r["case_id"]: r for r in data["results"]}
    suites = {c["suite"] for c in data["scope"]}
    if suites != {"baseline", "target"}:
        issues.append("declared scope must contain both baseline and target cases")
    for case in data["scope"]:
        case_id = case["case_id"]
        run = runs.get(case_id)
        if run is None:
            issues.append(f"{case_id}: missing result")
            continue
        bound = run["candidate_sha"] == data["release"]["candidate_sha"] and run["environment"] == data["release"]["environment"]
        if not bound:
            issues.append(f"{case_id}: candidate/environment mismatch")
        age = now - parse_time(run["observed_at"])
        fresh = -timedelta(minutes=policy.future_tolerance_minutes) <= age <= timedelta(hours=policy.max_age_hours)
        if not fresh:
            issues.append(f"{case_id}: stale or future evidence")
        reviewed = run["review"] == "approved" and bool(run["evidence_refs"])
        if not reviewed:
            issues.append(f"{case_id}: approved review and evidence references required")
        usable = run["status"] == "passed" or (run["status"] == "failed" and run["failure_kind"] == "product")
        if not usable:
            issues.append(f"{case_id}: execution incomplete or failure not confirmed as product")
        # A current confirmed critical failure blocks even when another case lacks evidence.
        if bound and fresh and reviewed and run["status"] == "failed" and run["failure_kind"] == "product" and case["criticality"] == "critical":
            blockers.append(f"{case_id}: confirmed critical product failure")
    for defect in data["defects"]:
        if defect["status"] == "open" and defect["severity"] == "P1":
            blockers.append(f"{defect['id']}: open P1 defect")
    for key, value in data["readiness"].items():
        if value is False or (isinstance(value, str) and not value.strip()):
            blockers.append(f"readiness: {key} required")

    result["evidence"]["status"] = "INSUFFICIENT" if issues else "COMPLETE"
    if blockers:
        result["decision"] = "NO_GO"
        result["risk"]["status"] = "BLOCKED"
        return result
    if issues:
        return result

    contributions = result["risk"]["contributions"]
    conditional_required = False
    for defect in data["defects"]:
        if defect["status"] == "open":
            points = policy.p2_points if defect["severity"] == "P2" else policy.p3_points
            contributions.append({"reason": f"{defect['id']}: open {defect['severity']}", "points": points})
            conditional_required |= defect["severity"] == "P2"
    for case in data["scope"]:
        run = runs[case["case_id"]]
        if run["status"] == "failed":
            points = getattr(policy, f"{case['criticality']}_failure_points")
            contributions.append({"reason": f"{case['case_id']}: product failure", "points": points})
            conditional_required = True
        if run["flaky"]:
            contributions.append({"reason": f"{case['case_id']}: flaky run", "points": policy.flaky_points})
            conditional_required = True
    score = min(sum(c["points"] for c in contributions), 100)
    result["risk"].update(status="ASSESSED", score=score)
    result["decision"] = classify_risk(score, conditional_required, policy)
    if result["decision"] == "CONDITIONAL_GO":
        acceptance = data["conditional_acceptance"]
        if (acceptance is None or not _text(acceptance["approved_by"]) or not _text(acceptance["mitigation"])
                or parse_time(acceptance["expires_at"]) <= now):
            blockers.append("conditional release requires a named approver, mitigation and unexpired acceptance")
            result["decision"] = "NO_GO"
            result["risk"]["status"] = "BLOCKED"
        else:
            result["conditions"].append(acceptance.copy())
    return result
