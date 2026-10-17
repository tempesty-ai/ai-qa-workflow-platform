"""Proposed impact-based severity rubric, separate from scheduling priority."""
from __future__ import annotations

POLICY_ID = "tms-severity-proposal-v1"
IMPACT_FIELDS = (
    "data_loss", "security_violation", "incorrect_financial_effect",
    "core_journey_blocked", "workaround_verified", "major_function_impacted", "minor_only",
)
GATE_LABEL = {"S1": "P1", "S2": "P2", "S3": "P3"}


def assess_severity(defect: dict) -> dict:
    result = {"policy_id": POLICY_ID, "severity": "UNCLASSIFIED", "rule": "insufficient_facts",
              "reason": "Impact facts, supporting evidence and an assessor are required."}
    if not isinstance(defect, dict):
        return result
    impact = defect.get("impact")
    if not isinstance(impact, dict) or set(impact) != set(IMPACT_FIELDS):
        return result
    if any(v is not None and type(v) is not bool for v in impact.values()):
        return result
    if defect.get("affected_scope") not in ("all", "subset", "single", "unknown"):
        return result
    if not all(isinstance(defect.get(k), str) and defect[k].strip() for k in ("assessed_by", "assessment_note")):
        return result
    refs = defect.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(v, str) and v.strip() for v in refs):
        return result

    def classified(level, rule, reason):
        return {"policy_id": POLICY_ID, "severity": level, "rule": rule, "reason": reason}

    # A confirmed severe effect is not diluted by low frequency or limited scope.
    if any(impact[k] is True for k in ("data_loss", "security_violation", "incorrect_financial_effect")):
        return classified("S1", "severe_customer_harm", "Confirmed data loss, security violation or incorrect financial effect.")
    if impact["core_journey_blocked"] is True and impact["workaround_verified"] is False:
        return classified("S1", "core_journey_without_workaround", "Core journey blocked without a verified workaround.")
    if any(v is None for v in impact.values()) or defect["affected_scope"] == "unknown":
        return result
    if impact["minor_only"] and (impact["core_journey_blocked"] or impact["major_function_impacted"]):
        return {**result, "reason": "Minor-only and major/core impact declarations contradict each other."}
    if impact["core_journey_blocked"] or impact["major_function_impacted"]:
        return classified("S2", "major_function_impact", "Major function impaired; no confirmed S1 condition.")
    if impact["minor_only"]:
        return classified("S3", "minor_only", "Only minor presentation/usability impact; core function, data and security unaffected.")
    return {**result, "reason": "No supported defect impact classification was established."}
