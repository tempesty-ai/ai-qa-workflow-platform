from __future__ import annotations

from pathlib import Path

import streamlit as st

from gate.data_loader import load_csv, load_json
from gate.release_gate import decide_gate


ROOT = Path(__file__).resolve().parents[1]


st.set_page_config(page_title="QA Release Gate", layout="wide")
st.title("QA Release Gate")

release = load_json(ROOT / "data" / "release_sample.json")
defects = load_csv(ROOT / "data" / "defects_sample.csv")
test_results = load_csv(ROOT / "data" / "test_results_sample.csv")
result = decide_gate(release, defects, test_results)

status_color = {
    "GO": "green",
    "CONDITIONAL_GO": "orange",
    "NO_GO": "red"
}[result.status]

st.markdown(f"### 판정: :{status_color}[{result.status}]")
st.metric("Risk Score", f"{result.score} / 100")
st.write(result.summary)

coverage = release["automation_coverage"]
signals = release["quality_signals"]
business = release["business_window"]
readiness = release["release_readiness"]

metric_cols = st.columns(4)
metric_cols[0].metric("Critical Flow Coverage", f"{coverage['critical_flow']}%")
metric_cols[1].metric("Smoke Pass Rate", f"{signals['smoke_pass_rate']}%")
metric_cols[2].metric("Blocked Tests", signals["blocked_test_count"])
metric_cols[3].metric("Flaky Tests", signals["flaky_test_count"])

left, right = st.columns(2)

with left:
    st.subheader("주요 리스크")
    for risk in result.top_risks:
        st.write(f"- {risk.reason} (+{risk.points})")

with right:
    st.subheader("권장 QA 액션")
    for action in result.recommended_actions:
        st.write(f"- {action}")

st.subheader("릴리즈 변경 범위")
st.dataframe(release["change_scope"], use_container_width=True)

st.subheader("릴리즈 준비 상태")
st.dataframe(
    [
        {"item": "customer_support_ready", "ready": business["customer_support_ready"]},
        {"item": "monitoring_owner_ready", "ready": business["monitoring_owner_ready"]},
        {"item": "rollback_plan_ready", "ready": business["rollback_plan_ready"]},
        {"item": "rollback_tested", "ready": business["rollback_tested"]},
        {"item": "qa_signoff_ready", "ready": readiness["qa_signoff_ready"]},
        {"item": "operations_approval", "ready": readiness["operations_approval"]},
        {"item": "known_issues_documented", "ready": readiness["known_issues_documented"]}
    ],
    use_container_width=True
)

st.subheader("미해결 결함")
st.dataframe([defect for defect in defects if defect["status"] == "open"], use_container_width=True)

st.subheader("테스트 결과")
st.dataframe(test_results, use_container_width=True)
