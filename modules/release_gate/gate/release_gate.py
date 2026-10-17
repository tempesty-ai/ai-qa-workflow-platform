from __future__ import annotations

from dataclasses import dataclass

from gate.risk_model import RiskItem, calculate_risk_score


@dataclass(frozen=True)
class GateResult:
    status: str
    score: int
    summary: str
    top_risks: list[RiskItem]
    recommended_actions: list[str]


def decide_gate(release: dict, defects: list[dict[str, str]], test_results: list[dict[str, str]]) -> GateResult:
    score, risks = calculate_risk_score(release, defects, test_results)
    open_p1 = [defect for defect in defects if defect.get("status") == "open" and defect.get("severity") == "P1"]
    failed_critical = [
        result for result in test_results
        if result.get("status") == "failed" and result.get("criticality") == "critical"
    ]
    blocked_critical = [
        result for result in test_results
        if result.get("status") == "blocked" and result.get("criticality") == "critical"
    ]
    qa_signoff_ready = release.get("release_readiness", {}).get("qa_signoff_ready", False)

    if open_p1 or failed_critical or blocked_critical or score >= 80:
        status = "NO_GO"
        summary = "핵심 결함, critical 테스트 실패/차단, 또는 높은 종합 리스크로 릴리즈 보류가 필요합니다."
    elif not qa_signoff_ready or score >= 45:
        status = "CONDITIONAL_GO"
        summary = "릴리즈는 가능할 수 있지만 조건부 승인, 보강 테스트, 강화 모니터링이 필요합니다."
    else:
        status = "GO"
        summary = "현재 기준에서는 릴리즈 진행이 가능합니다."

    return GateResult(
        status=status,
        score=score,
        summary=summary,
        top_risks=risks[:8],
        recommended_actions=recommend_actions(status, risks)
    )


def recommend_actions(status: str, risks: list[RiskItem]) -> list[str]:
    actions = []
    categories = {risk.category for risk in risks}

    if "open_defect" in categories:
        actions.append("P1/P2 미해결 결함의 고객 영향, 우회 가능 여부, target fix를 재확인합니다.")
    if "failed_test" in categories or "blocked_test" in categories:
        actions.append("실패/차단된 smoke, regression, visual 테스트를 수정 후 재실행합니다.")
    if "flaky_test" in categories:
        actions.append("Flaky warning은 단순 통과로 보지 말고 재현 조건과 최근 성공 build를 확인합니다.")
    if "change_scope" in categories:
        actions.append("결제/인증 등 핵심 변경 영역은 배포 후 집중 모니터링 대상으로 지정합니다.")
    if "coverage" in categories:
        actions.append("자동화 커버리지가 낮은 변경 영역은 수동 보강 테스트 evidence를 남깁니다.")
    if "quality_signal" in categories:
        actions.append("Pass rate, blocked count, flaky count를 릴리즈 노트의 품질 신호로 기록합니다.")
    if "readiness" in categories or "business_window" in categories:
        actions.append("QA sign-off, 운영 승인, rollback test, 모니터링 담당자 준비 상태를 완료합니다.")

    if status == "NO_GO":
        actions.append("릴리즈 책임자, QA, 결함 owner가 함께 보류 사유와 재시도 조건을 승인해야 합니다.")
    elif status == "CONDITIONAL_GO":
        actions.append("조건부 승인 항목과 rollback 기준을 릴리즈 노트에 명시합니다.")
    else:
        actions.append("배포 후 기본 smoke check와 모니터링을 진행합니다.")

    return actions
