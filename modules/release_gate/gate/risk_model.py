from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskItem:
    category: str
    points: int
    reason: str


SEVERITY_POINTS = {
    "P1": 40,
    "P2": 15,
    "P3": 5
}

TEST_POINTS = {
    "critical": 20,
    "high": 12,
    "medium": 6,
    "low": 3
}

AREA_POINTS = {
    "critical": 15,
    "high": 10,
    "medium": 5,
    "low": 2
}

CUSTOMER_IMPACT_POINTS = {
    "high": 10,
    "medium": 5,
    "low": 2
}


def _as_int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _is_true(value: object) -> bool:
    return str(value).lower() == "true"


def score_open_defects(defects: list[dict[str, str]]) -> list[RiskItem]:
    items: list[RiskItem] = []
    for defect in defects:
        if defect.get("status") != "open":
            continue

        severity = defect.get("severity", "")
        points = SEVERITY_POINTS.get(severity, 0)
        points += CUSTOMER_IMPACT_POINTS.get(defect.get("customer_impact", "low"), 0)

        if _is_true(defect.get("reopened")):
            points += 5
        if defect.get("workaround") == "false":
            points += 8
        if _as_int(defect.get("age_days")) >= 7:
            points += 4
        if defect.get("verified_by_qa") == "false" and severity in {"P1", "P2"}:
            points += 5

        items.append(
            RiskItem(
                category="open_defect",
                points=points,
                reason=f"{defect.get('id')} {severity} 미해결: {defect.get('title')} ({defect.get('affected_flow')})"
            )
        )
    return items


def score_test_results(test_results: list[dict[str, str]]) -> list[RiskItem]:
    items: list[RiskItem] = []
    for result in test_results:
        status = result.get("status")
        criticality = result.get("criticality", "low")
        case_name = result.get("case_name")
        area = result.get("area")

        if status == "failed":
            points = TEST_POINTS.get(criticality, 3)
            if result.get("execution_type") == "manual":
                points += 3
            if _is_true(result.get("flaky")):
                points += 4
            items.append(
                RiskItem(
                    category="failed_test",
                    points=points,
                    reason=f"{result.get('id')} 실패: {case_name} ({area}, {criticality})"
                )
            )
        elif status == "blocked":
            points = TEST_POINTS.get(criticality, 3) + 8
            items.append(
                RiskItem(
                    category="blocked_test",
                    points=points,
                    reason=f"{result.get('id')} 차단: {case_name} ({area}, {criticality})"
                )
            )
        elif status == "warning" and _is_true(result.get("flaky")):
            items.append(
                RiskItem(
                    category="flaky_test",
                    points=5,
                    reason=f"{result.get('id')} flaky warning: {case_name} ({area})"
                )
            )
    return items


def score_change_scope(release: dict) -> list[RiskItem]:
    items: list[RiskItem] = []
    for change in release.get("change_scope", []):
        criticality = change.get("criticality", "low")
        change_size = change.get("change_size", "small")
        points = AREA_POINTS.get(criticality, 2)
        if change_size == "large":
            points += 10
        elif change_size == "medium":
            points += 5
        if change.get("external_dependency"):
            points += 4
        if change.get("requires_data_migration"):
            points += 10

        items.append(
            RiskItem(
                category="change_scope",
                points=points,
                reason=f"{change.get('area')} 변경 범위: {criticality}/{change_size}"
            )
        )
    return items


def score_coverage(release: dict) -> list[RiskItem]:
    coverage = release.get("automation_coverage", {})
    overall = _as_int(coverage.get("overall"))
    critical_flow = _as_int(coverage.get("critical_flow"))
    changed_area = _as_int(coverage.get("changed_area"))
    items: list[RiskItem] = []

    if overall < 70:
        items.append(RiskItem("coverage", 10, f"전체 자동화 커버리지 낮음: {overall}%"))
    if critical_flow < 65:
        items.append(RiskItem("coverage", 15, f"핵심 플로우 자동화 커버리지 낮음: {critical_flow}%"))
    if changed_area < 70:
        items.append(RiskItem("coverage", 10, f"변경 영역 자동화 커버리지 낮음: {changed_area}%"))
    if not coverage.get("manual_supplement_done", False):
        items.append(RiskItem("coverage", 8, "자동화 부족 영역의 수동 보강 테스트 미완료"))

    return items


def score_quality_signals(release: dict) -> list[RiskItem]:
    signals = release.get("quality_signals", {})
    items: list[RiskItem] = []

    if _as_int(signals.get("smoke_pass_rate"), 100) < 90:
        items.append(RiskItem("quality_signal", 12, f"Smoke pass rate 낮음: {signals.get('smoke_pass_rate')}%"))
    if _as_int(signals.get("regression_pass_rate"), 100) < 85:
        items.append(RiskItem("quality_signal", 10, f"Regression pass rate 낮음: {signals.get('regression_pass_rate')}%"))
    if _as_int(signals.get("api_pass_rate"), 100) < 90:
        items.append(RiskItem("quality_signal", 8, f"API pass rate 낮음: {signals.get('api_pass_rate')}%"))

    flaky_count = _as_int(signals.get("flaky_test_count"))
    blocked_count = _as_int(signals.get("blocked_test_count"))
    if flaky_count:
        items.append(RiskItem("quality_signal", flaky_count * 3, f"Flaky test 존재: {flaky_count}건"))
    if blocked_count:
        items.append(RiskItem("quality_signal", blocked_count * 8, f"Blocked test 존재: {blocked_count}건"))

    return items


def score_release_readiness(release: dict) -> list[RiskItem]:
    business = release.get("business_window", {})
    readiness = release.get("release_readiness", {})
    items: list[RiskItem] = []

    if business.get("peak_season"):
        items.append(RiskItem("business_window", 10, "Peak season 배포"))
    if business.get("campaign_active"):
        items.append(RiskItem("business_window", 8, "Campaign 진행 중 배포"))
    if not business.get("monitoring_owner_ready", False):
        items.append(RiskItem("readiness", 12, "모니터링 owner 준비 미완료"))
    if not business.get("rollback_plan_ready", False):
        items.append(RiskItem("readiness", 15, "Rollback plan 미준비"))
    elif not business.get("rollback_tested", False):
        items.append(RiskItem("readiness", 8, "Rollback plan은 있으나 테스트 미완료"))

    if not readiness.get("qa_signoff_ready", False):
        items.append(RiskItem("readiness", 12, "QA sign-off 미완료"))
    if not readiness.get("operations_approval", False):
        items.append(RiskItem("readiness", 8, "운영 승인 미완료"))
    if not readiness.get("known_issues_documented", False):
        items.append(RiskItem("readiness", 6, "Known issue 문서화 미완료"))

    return items


def calculate_risk_score(
    release: dict,
    defects: list[dict[str, str]],
    test_results: list[dict[str, str]]
) -> tuple[int, list[RiskItem]]:
    items = [
        *score_open_defects(defects),
        *score_test_results(test_results),
        *score_change_scope(release),
        *score_coverage(release),
        *score_quality_signals(release),
        *score_release_readiness(release)
    ]
    score = min(sum(item.points for item in items), 100)
    return score, sorted(items, key=lambda item: item.points, reverse=True)
