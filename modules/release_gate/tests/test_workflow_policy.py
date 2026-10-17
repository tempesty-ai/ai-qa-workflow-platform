import copy
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path

import pytest

from gate.workflow_policy import Policy, classify_risk, evaluate_workflow, parse_time
from run_workflow_gate import main, read_json


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "workflow"
NOW = parse_time("2026-10-16T00:00:00Z")


@pytest.fixture
def evidence():
    return json.loads((EXAMPLES / "go.json").read_text(encoding="utf-8"))


def evaluate(data, policy=None):
    return evaluate_workflow(data, policy, now=NOW)


@pytest.mark.parametrize("name,decision,code", [
    ("go", "GO", 0), ("conditional_go", "CONDITIONAL_GO", 3),
    ("no_go", "NO_GO", 1), ("evidence_insufficient", "EVIDENCE_INSUFFICIENT", 2),
])
def test_demo_cli_contract(name, decision, code, tmp_path):
    args = ["--input", str(EXAMPLES / f"{name}.json"), "--as-of", NOW.isoformat(),
            "--policy", str(EXAMPLES / "policy.json"), "--output-dir", str(tmp_path)]
    assert main(args + ["--strict"]) == code
    output = json.loads((tmp_path / "result.json").read_text())
    assert output["decision"] == decision
    assert output["policy"] == asdict(Policy())
    assert len(output["input_sha256"]) == 64
    assert decision in (tmp_path / "report.md").read_text()
    assert main(args) == 0


@pytest.mark.parametrize("score,decision", [(0, "GO"), (19, "GO"), (20, "CONDITIONAL_GO"),
                                           (44, "CONDITIONAL_GO"), (45, "NO_GO"), (100, "NO_GO")])
def test_threshold_boundaries(score, decision):
    assert classify_risk(score, False, Policy()) == decision


def test_configurable_thresholds_and_score_cap(evidence):
    evidence["defects"] = [{"id": f"SYNTHETIC-{i}", "severity": "P3", "status": "open"} for i in range(30)]
    assert evaluate(evidence)["risk"]["score"] == 100
    assert evaluate(evidence)["decision"] == "NO_GO"
    evidence["defects"] = evidence["defects"][:2]
    assert evaluate(evidence)["decision"] == "GO"
    assert evaluate(evidence, Policy(no_go_min=10, conditional_min=5))["decision"] == "NO_GO"


@pytest.mark.parametrize("overrides", [{"conditional_min": 45}, {"no_go_min": 101}, {"max_age_hours": 0},
    {"max_age_hours": float("nan")}, {"max_age_hours": float("inf")}, {"p2_points": -1},
    {"flaky_points": 0}, {"conditional_min": True}, {"conditional_min": 20.0},
    {"max_age_hours": "24"}, {"future_tolerance_minutes": 61}])
def test_invalid_policy_rejected(overrides):
    with pytest.raises(ValueError):
        Policy(**overrides)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(scope=[], results=[]),
    lambda d: d["results"].pop(),
    lambda d: d["results"][0].update(evidence_refs=[]),
    lambda d: d["results"][0].update(review="pending"),
    lambda d: d["results"][0].update(review="rejected"),
    lambda d: d["results"][0].update(status="blocked", failure_kind="environment"),
    lambda d: d["results"][0].update(status="not_run", failure_kind="unknown"),
    lambda d: d["results"][0].update(status="failed", failure_kind="automation"),
    lambda d: d["results"][0].update(status="failed", failure_kind="unknown"),
    lambda d: d["results"][0].update(candidate_sha="b" * 40),
    lambda d: d["results"][0].update(environment="another-demo"),
    lambda d: d["results"][0].update(observed_at="2026-10-14T23:59:59Z"),
    lambda d: d["results"][0].update(observed_at="2026-10-16T00:05:01Z"),
    lambda d: d["results"].append(copy.deepcopy(d["results"][0])),
    lambda d: d["scope"].append(copy.deepcopy(d["scope"][0])),
    lambda d: d["results"][0].update(case_id="OUT-OF-SCOPE"),
    lambda d: d["results"][0].update(status="PASS"),
    lambda d: d["results"][0].update(flaky="false"),
    lambda d: d["results"][0].update(failure_kind="environment"),
    lambda d: d["results"][0].update(observed_at="2026-10-16T00:00:00"),
    lambda d: d["defects"].append({"id": "SYNTHETIC-1", "severity": "unknown", "status": "open"}),
    lambda d: d["readiness"].update(qa_signoff="true"),
    lambda d: d.update(synthetic=False),
    lambda d: d.update(schema_version=True),
    lambda d: d.update(unexpected="field"),
    lambda d: d.pop("defects"),
])
def test_missing_or_invalid_evidence_never_becomes_zero_risk_go(evidence, mutation):
    mutation(evidence)
    result = evaluate(evidence)
    assert result["decision"] == "EVIDENCE_INSUFFICIENT"
    assert result["evidence"]["status"] == "INSUFFICIENT"
    assert result["evidence"]["issues"]
    assert result["risk"]["score"] is None


@pytest.mark.parametrize("offset", [timedelta(hours=-24), timedelta(minutes=5)])
def test_freshness_boundaries_inclusive(evidence, offset):
    evidence["results"][0]["observed_at"] = (NOW + offset).isoformat()
    assert evaluate(evidence)["decision"] == "GO"


def test_age_configuration(evidence):
    evidence["results"][0]["observed_at"] = (NOW - timedelta(hours=2)).isoformat()
    assert evaluate(evidence, Policy(max_age_hours=1))["decision"] == "EVIDENCE_INSUFFICIENT"


@pytest.mark.parametrize("kind", ["p1", "critical"])
def test_hard_blocker_wins_over_incomplete_other_evidence(evidence, kind):
    if kind == "p1":
        evidence["defects"].append({"id": "SYNTHETIC-P1", "severity": "P1", "status": "open"})
    else:
        evidence["results"][0].update(status="failed", failure_kind="product")
    evidence["results"].pop()
    result = evaluate(evidence, Policy(conditional_min=98, no_go_min=99))
    assert result["decision"] == "NO_GO"
    assert result["evidence"]["status"] == "INSUFFICIENT"
    assert result["risk"]["blockers"]
    assert result["risk"]["score"] is None


def test_stale_critical_failure_is_not_current_confirmed_failure(evidence):
    evidence["results"][0].update(status="failed", failure_kind="product", observed_at="2026-10-01T00:00:00Z")
    assert evaluate(evidence)["decision"] == "EVIDENCE_INSUFFICIENT"


@pytest.mark.parametrize("key,value", [("qa_signoff", False), ("operations_approval", False),
    ("rollback_tested", False), ("monitoring_owner", " "), ("rollback_trigger", "")])
def test_readiness_is_a_hard_requirement(evidence, key, value):
    evidence["readiness"][key] = value
    result = evaluate(evidence)
    assert result["decision"] == "NO_GO"
    assert result["evidence"]["status"] == "COMPLETE"


@pytest.mark.parametrize("trigger", ["p2", "product_failure", "flaky"])
def test_residual_high_signal_requires_conditional_even_below_threshold(evidence, trigger):
    if trigger == "p2":
        evidence["defects"] = [{"id": "SYNTHETIC-P2", "severity": "P2", "status": "open"}]
    elif trigger == "product_failure":
        evidence["results"][1].update(status="failed", failure_kind="product")
    else:
        evidence["results"][1]["flaky"] = True
    assert evaluate(evidence)["decision"] == "NO_GO"  # no acceptance
    evidence["conditional_acceptance"] = {"approved_by": "Synthetic approver", "mitigation": "Demo mitigation", "expires_at": "2026-10-17T00:00:00Z"}
    assert evaluate(evidence)["decision"] == "CONDITIONAL_GO"
    assert evaluate(evidence)["risk"]["score"] < 20


@pytest.mark.parametrize("acceptance", [None,
    {"approved_by": "", "mitigation": "Demo mitigation", "expires_at": "2026-10-17T00:00:00Z"},
    {"approved_by": "Synthetic approver", "mitigation": " ", "expires_at": "2026-10-17T00:00:00Z"},
    {"approved_by": "Synthetic approver", "mitigation": "Demo mitigation", "expires_at": "2026-10-16T00:00:00Z"}])
def test_conditional_acceptance_cannot_be_missing_or_expired(evidence, acceptance):
    evidence["defects"] = [{"id": "SYNTHETIC-P2", "severity": "P2", "status": "open"}]
    evidence["conditional_acceptance"] = acceptance
    result = evaluate(evidence)
    assert result["decision"] == "NO_GO"
    assert result["evidence"]["status"] == "COMPLETE"


def test_resolved_defect_and_input_immutability(evidence):
    evidence["defects"] = [{"id": "SYNTHETIC-P1", "severity": "P1", "status": "resolved"}]
    before = copy.deepcopy(evidence)
    assert evaluate(evidence)["decision"] == "GO"
    assert evidence == before


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_ambiguous_json_rejected(raw):
    with pytest.raises(ValueError):
        read_json(raw)


@pytest.mark.parametrize("raw", [b"{broken", b"\xff", b"[]", b"null"])
def test_malformed_input_produces_insufficient_report(raw, tmp_path):
    source = tmp_path / "input.json"
    source.write_bytes(raw)
    assert main(["--input", str(source), "--output-dir", str(tmp_path), "--strict"]) == 2
    assert json.loads((tmp_path / "result.json").read_text())["risk"]["score"] is None


def test_missing_input_and_invalid_config_fail_closed(tmp_path):
    assert main(["--input", str(tmp_path / "missing"), "--output-dir", str(tmp_path), "--strict"]) == 2
    config = tmp_path / "policy.json"
    config.write_text('{"typo_threshold": 2}')
    assert main(["--input", str(EXAMPLES / "go.json"), "--policy", str(config)]) == 4
    assert main(["--input", str(EXAMPLES / "go.json"), "--as-of", "2026-10-16"]) == 4
