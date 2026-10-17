from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest

from modules.release_gate.gate.workflow_policy import parse_time
from tms.__main__ import main
from tms.engine import (SCENARIOS, STRICT_EXIT, evaluate_run, execute_synthetic, load_run,
                        review_case, snapshot_digest, write_json)
from tms.severity import IMPACT_FIELDS, assess_severity

NOW = parse_time("2026-10-17T00:00:00Z")


def defect(**impact):
    return {"id": "SYNTHETIC-1", "impact": {**dict.fromkeys(IMPACT_FIELDS, False), "minor_only": True, **impact},
            "affected_scope": "single", "evidence_refs": ["synthetic-evidence"],
            "assessed_by": "Synthetic assessor", "assessment_note": "Synthetic impact classification", "priority": "normal"}


@pytest.mark.parametrize("impact,level", [
    ({"data_loss": True}, "S1"), ({"security_violation": True}, "S1"),
    ({"incorrect_financial_effect": True}, "S1"),
    ({"minor_only": False, "core_journey_blocked": True, "workaround_verified": False}, "S1"),
    ({"minor_only": False, "core_journey_blocked": True, "workaround_verified": True}, "S2"),
    ({"minor_only": False, "major_function_impacted": True}, "S2"),
    ({}, "S3"), ({"minor_only": False}, "UNCLASSIFIED"),
    ({"major_function_impacted": True}, "UNCLASSIFIED"),
    ({"workaround_verified": None}, "UNCLASSIFIED"),
    ({"data_loss": "false"}, "UNCLASSIFIED"),
])
def test_impact_rubric(impact, level):
    assert assess_severity(defect(**impact))["severity"] == level


@pytest.mark.parametrize("field,value", [("assessed_by", ""), ("assessment_note", " "),
    ("evidence_refs", []), ("affected_scope", "unknown"), ("impact", {})])
def test_classification_requires_explained_facts(field, value):
    item = defect()
    item[field] = value
    assert assess_severity(item)["severity"] == "UNCLASSIFIED"


def test_known_severe_harm_is_not_downgraded_by_scope_priority_or_other_unknowns():
    item = defect(security_violation=True, workaround_verified=None)
    item.update(affected_scope="unknown", priority="deferred")
    assert assess_severity(item)["severity"] == "S1"
    for priority in ("urgent", "normal", "deferred"):
        ordinary = defect()
        ordinary["priority"] = priority
        assert assess_severity(ordinary)["severity"] == "S3"


def approve_all(directory, now=NOW):
    for case in ("BASE-001", "TARGET-001"):
        review_case(directory, case, "Synthetic reviewer", "approved", "Checked synthetic assertions", now=now)


@pytest.mark.parametrize("scenario,expected", SCENARIOS.items())
def test_full_flow_executes_assertions_and_separates_reviews(tmp_path, scenario, expected):
    run = execute_synthetic(scenario, tmp_path, now=NOW)
    before = evaluate_run(tmp_path, now=NOW)
    assert before["decision"] == ("NO_GO" if scenario == "no_go" else "EVIDENCE_INSUFFICIENT")
    assert all(r["review"] == "pending" for r in run["results"])
    approve_all(tmp_path)
    result = evaluate_run(tmp_path, now=NOW)
    assert result["decision"] == expected
    assert (tmp_path / "gate-input.json").exists()
    assert (tmp_path / "report.md").exists()
    evidence = json.loads((tmp_path / "evidence/TARGET-001.json").read_text(encoding="utf-8"))
    if scenario == "conditional":
        assert len(evidence["observed_rows"]) == 6
        assert not all(a["passed"] for a in evidence["assertions"])
        assert result["risk"]["score"] == 27  # S2/P2 15 + high failure 12
        assert result["tms"]["severity_assessments"][0]["severity"] == "S2"
    elif scenario == "go":
        assert len(evidence["observed_rows"]) == 2
        assert all(r["level"] == "warning" for r in evidence["observed_rows"])


def test_review_changes_preserve_snapshot_and_cannot_imply_test_pass(tmp_path):
    execute_synthetic("insufficient", tmp_path, now=NOW)
    digest = snapshot_digest(load_run(tmp_path))
    approve_all(tmp_path)
    assert snapshot_digest(load_run(tmp_path)) == digest
    assert evaluate_run(tmp_path, now=NOW)["decision"] == "EVIDENCE_INSUFFICIENT"


def test_artifact_tampering_invalidates_reviews_and_new_approval(tmp_path):
    execute_synthetic("go", tmp_path, now=NOW)
    approve_all(tmp_path)
    artifact = tmp_path / "evidence/TARGET-001.json"
    artifact.write_text('{"tampered":true}')
    result = evaluate_run(tmp_path, now=NOW)
    assert result["decision"] == "EVIDENCE_INSUFFICIENT"
    assert any("digest mismatch" in x for x in result["evidence"]["issues"])
    with pytest.raises(ValueError, match="digest mismatch"):
        approve_all(tmp_path)


def test_result_mutation_invalidates_previous_snapshot_review(tmp_path):
    execute_synthetic("go", tmp_path, now=NOW)
    approve_all(tmp_path)
    run = load_run(tmp_path)
    run["release"]["candidate_sha"] = "b" * 40
    for result in run["results"]:
        result["candidate_sha"] = "b" * 40
    write_json(tmp_path / "run.json", run)
    assert evaluate_run(tmp_path, now=NOW)["decision"] == "EVIDENCE_INSUFFICIENT"


def test_latest_rejection_overrides_approval(tmp_path):
    execute_synthetic("go", tmp_path, now=NOW)
    approve_all(tmp_path)
    review_case(tmp_path, "TARGET-001", "Synthetic reviewer", "rejected", "Needs evidence repair", now=NOW)
    assert evaluate_run(tmp_path, now=NOW)["decision"] == "EVIDENCE_INSUFFICIENT"


def test_review_cannot_predate_execution_or_exceed_clock_skew(tmp_path):
    execute_synthetic("go", tmp_path, now=NOW)
    approve_all(tmp_path, now=NOW - timedelta(seconds=1))
    assert evaluate_run(tmp_path, now=NOW)["decision"] == "EVIDENCE_INSUFFICIENT"
    approve_all(tmp_path, now=NOW + timedelta(minutes=6))
    assert evaluate_run(tmp_path, now=NOW)["decision"] == "EVIDENCE_INSUFFICIENT"


def test_unclassified_impact_does_not_become_low_risk(tmp_path):
    execute_synthetic("conditional", tmp_path, now=NOW)
    run = load_run(tmp_path)
    run["defects"][0]["impact"]["data_loss"] = None
    write_json(tmp_path / "run.json", run)
    approve_all(tmp_path)
    result = evaluate_run(tmp_path, now=NOW)
    assert result["decision"] == "EVIDENCE_INSUFFICIENT"
    assert result["risk"]["score"] is None


def test_known_s1_blocks_even_when_another_defect_is_unclassified(tmp_path):
    execute_synthetic("no_go", tmp_path, now=NOW)
    run = load_run(tmp_path)
    other = deepcopy(run["defects"][0])
    other["id"] = "SYNTHETIC-UNKNOWN"
    other["impact"] = dict.fromkeys(IMPACT_FIELDS, None)
    run["defects"].append(other)
    write_json(tmp_path / "run.json", run)
    result = evaluate_run(tmp_path, now=NOW)
    assert result["decision"] == "NO_GO"
    assert result["evidence"]["status"] == "INSUFFICIENT"


def test_expired_acceptance_and_stale_evidence_hold(tmp_path):
    execute_synthetic("conditional", tmp_path, now=NOW)
    approve_all(tmp_path)
    assert evaluate_run(tmp_path, now=NOW + timedelta(hours=2))["decision"] == "NO_GO"
    assert evaluate_run(tmp_path, now=NOW + timedelta(hours=25))["decision"] == "EVIDENCE_INSUFFICIENT"


def test_no_run_overwrite_and_no_evidence_path_escape(tmp_path):
    execute_synthetic("go", tmp_path, now=NOW)
    with pytest.raises(ValueError, match="already exists"):
        execute_synthetic("go", tmp_path, now=NOW)
    run = load_run(tmp_path)
    run["evidence_manifest"][0]["path"] = "../outside.json"
    write_json(tmp_path / "run.json", run)
    result = evaluate_run(tmp_path, now=NOW)
    assert result["decision"] == "EVIDENCE_INSUFFICIENT"
    assert any("outside run" in x for x in result["evidence"]["issues"])


@pytest.mark.parametrize("scenario,expected", SCENARIOS.items())
def test_cli_strict_exits(tmp_path, scenario, expected):
    assert main(["demo", "--scenario", scenario, "--output-dir", str(tmp_path)]) == 0
    directory = tmp_path / scenario
    assert main(["gate", "--run-dir", str(directory), "--strict"]) == STRICT_EXIT[expected]


def test_cli_run_and_explicit_review(tmp_path):
    assert main(["run", "--output-dir", str(tmp_path)]) == 0
    assert main(["gate", "--run-dir", str(tmp_path), "--strict"]) == 2
    for case in ("BASE-001", "TARGET-001"):
        assert main(["review", "--run-dir", str(tmp_path), "--case", case, "--reviewer", "Synthetic reviewer",
                     "--decision", "approved", "--note", "Synthetic evidence inspected"]) == 0
    assert main(["gate", "--run-dir", str(tmp_path), "--strict"]) == 0


def test_cli_malformed_run_and_policy_fail_closed(tmp_path):
    assert main(["gate", "--run-dir", str(tmp_path), "--strict"]) == 2
    (tmp_path / "run.json").write_text('{"synthetic":true,"synthetic":false}')
    assert main(["gate", "--run-dir", str(tmp_path), "--strict"]) == 2
    config = tmp_path / "invalid-policy.json"
    config.write_text('{"no_go_min":-1}')
    assert main(["gate", "--run-dir", str(tmp_path), "--strict", "--policy", str(config)]) == 4
    config.write_text('{"no_go_min":45,"no_go_min":60}')
    assert main(["gate", "--run-dir", str(tmp_path), "--strict", "--policy", str(config)]) == 4
