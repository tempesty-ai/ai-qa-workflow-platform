from gate.risk_model import calculate_risk_score


def test_calculate_risk_score_caps_at_100() -> None:
    release = {
        "change_scope": [
            {"area": "payment", "criticality": "critical", "change_size": "large"}
        ],
        "automation_coverage": {"overall": 40, "critical_flow": 30, "changed_area": 30, "manual_supplement_done": False},
        "quality_signals": {"smoke_pass_rate": 70, "regression_pass_rate": 70, "api_pass_rate": 80, "flaky_test_count": 2, "blocked_test_count": 1},
        "business_window": {"campaign_active": True, "monitoring_owner_ready": False, "rollback_plan_ready": False},
        "release_readiness": {"qa_signoff_ready": False, "operations_approval": False, "known_issues_documented": False}
    }
    defects = [
        {
            "id": "BUG-1",
            "title": "critical issue",
            "severity": "P1",
            "status": "open",
            "workaround": "false",
            "reopened": "true",
            "customer_impact": "high",
            "age_days": "10",
            "verified_by_qa": "false",
            "affected_flow": "checkout"
        },
        {
            "id": "BUG-2",
            "title": "major issue",
            "severity": "P2",
            "status": "open",
            "workaround": "false",
            "reopened": "true",
            "customer_impact": "medium",
            "age_days": "3",
            "verified_by_qa": "false",
            "affected_flow": "login"
        }
    ]
    tests = [
        {"id": "TC-1", "case_name": "checkout", "area": "payment", "criticality": "critical", "status": "failed", "execution_type": "automated", "flaky": "false"}
    ]

    score, risks = calculate_risk_score(release, defects, tests)

    assert score == 100
    assert risks[0].points >= risks[-1].points


def test_resolved_defects_do_not_add_risk() -> None:
    release = {
        "change_scope": [],
        "automation_coverage": {"overall": 90, "critical_flow": 90, "changed_area": 90, "manual_supplement_done": True},
        "quality_signals": {},
        "business_window": {"monitoring_owner_ready": True, "rollback_plan_ready": True, "rollback_tested": True},
        "release_readiness": {"qa_signoff_ready": True, "operations_approval": True, "known_issues_documented": True}
    }
    defects = [{"id": "BUG-1", "severity": "P1", "status": "resolved"}]
    tests = []

    score, risks = calculate_risk_score(release, defects, tests)

    assert score == 0
    assert risks == []


def test_blocked_critical_test_adds_risk() -> None:
    release = {
        "change_scope": [],
        "automation_coverage": {"overall": 90, "critical_flow": 90, "changed_area": 90, "manual_supplement_done": True},
        "quality_signals": {},
        "business_window": {"monitoring_owner_ready": True, "rollback_plan_ready": True, "rollback_tested": True},
        "release_readiness": {"qa_signoff_ready": True, "operations_approval": True, "known_issues_documented": True}
    }
    score, risks = calculate_risk_score(
        release,
        [],
        [{"id": "TC-9", "case_name": "guest_checkout", "area": "payment", "criticality": "critical", "status": "blocked"}]
    )

    assert score == 28
    assert risks[0].category == "blocked_test"
