from __future__ import annotations

from pathlib import Path

from gate.release_gate import GateResult


def render_markdown(result: GateResult, release: dict) -> str:
    risk_lines = "\n".join(
        f"- {risk.reason} (+{risk.points})"
        for risk in result.top_risks
    )
    action_lines = "\n".join(f"- {action}" for action in result.recommended_actions)
    coverage = release.get("automation_coverage", {})
    signals = release.get("quality_signals", {})
    readiness = release.get("release_readiness", {})
    business = release.get("business_window", {})

    return f"""# Release Gate Report

## 판정

| 항목 | 값 |
| --- | --- |
| Release | {release.get("release_id")} |
| Service | {release.get("service")} |
| Status | {result.status} |
| Risk Score | {result.score} / 100 |

{result.summary}

## 판단 근거 요약

| 항목 | 값 |
| --- | --- |
| 전체 자동화 커버리지 | {coverage.get("overall")}% |
| 핵심 플로우 커버리지 | {coverage.get("critical_flow")}% |
| 변경 영역 커버리지 | {coverage.get("changed_area")}% |
| Smoke pass rate | {signals.get("smoke_pass_rate")}% |
| Regression pass rate | {signals.get("regression_pass_rate")}% |
| Flaky test | {signals.get("flaky_test_count")}건 |
| Blocked test | {signals.get("blocked_test_count")}건 |
| QA sign-off | {readiness.get("qa_signoff_ready")} |
| 운영 승인 | {readiness.get("operations_approval")} |
| Rollback tested | {business.get("rollback_tested")} |

## 주요 리스크

{risk_lines}

## 권장 QA 액션

{action_lines}
"""


def write_report(result: GateResult, release: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(result, release), encoding="utf-8")
    return path
