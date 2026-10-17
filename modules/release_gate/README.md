# QA Release Gate — 릴리즈 리스크 판단 & 배포 승인 대시보드

> 테스트 결과, 미해결 결함, 변경 범위, 자동화 커버리지를 종합해 **이번 릴리즈를 배포해도 되는지** `GO / CONDITIONAL_GO / NO_GO`로 판정하는 QA 의사결정 프로젝트.
> 핵심은 "테스트를 많이 돌리는 것"이 아니라, **"릴리즈 리스크를 설명 가능한 기준으로 판단하는 것"** 입니다.

---

## 한 줄 가치

> **"이 릴리즈가 나가도 되는지 어떤 근거로 판단했는가?"** 라는 질문에 점수와 항목별 기여도로 답하는 저장소.
> 시니어 QA의 머릿속에만 있던 판단을 **데이터 · 룰 · 리포트 · 대시보드 · CI**로 분리해 보여줍니다.

---

## 데이터 안내

이 저장소의 릴리즈 정보, 결함, 테스트 결과, 변경 범위는 모두 직접 만든 **가상 샘플 데이터**입니다. 현재 또는 과거 회사/고객사의 이슈, 운영 지표, 릴리즈 기록, 결함 데이터는 포함하지 않습니다.

## Baseline·Target 증거 연동 — 제안 정책 v1

[AI QA Workflow Platform](https://github.com/tempesty-ai/ai-qa-workflow-platform)의 공개 설명을
합성 데이터 기반의 [실행 데모](examples/workflow/README.md)로 연결했습니다.
새 정책은 **증거 충족도**와 **출시 위험**을 분리하며, `GO / CONDITIONAL_GO / NO_GO`와
`EVIDENCE_INSUFFICIENT`를 구분합니다. 미실행·미검수·환경 오류를 통과로 간주하지 않습니다.

기본 경계 20/45점, 증거 유효기간 24시간은 **검토·조정을 위한 제안**입니다. 보편적인 품질 기준이나
실제 제품의 배포 승인이 아닙니다. [정책·예외·한계](docs/workflow-quality-gate-policy.md)를 먼저 확인하세요.

```bash
python run_workflow_gate.py --input examples/workflow/go.json --as-of 2026-10-16T00:00:00Z --strict
```

이하의 CSV 엔진·대시보드·45/80점 정책과 `run_gate.py` 동작은 그대로 유지합니다.
새 데모의 엄격 모드는 조건부 판정도 종료 코드 3으로 보류하며, 증거 부족은 2로 보류합니다.
`Workflow Evidence Demo` CI는 네 가지 예상 판정과 종료 코드를 검증하고 보고서를 보관합니다.
기존 `QA Release Gate` CI는 NO_GO인 기존 샘플로 실행하므로 계속 실패합니다. 데모 CI의 성공과
실제 릴리즈 승인·필수 머지 검사는 별도입니다.

플랫폼에서 이 계약을 소비하는 변경은 [연동 PR](https://github.com/tempesty-ai/ai-qa-workflow-platform/pull/1)과
[고정 버전 실행 안내](https://github.com/tempesty-ai/ai-qa-workflow-platform/blob/caf4c60a6e6b886a39c5de86b37c88dc60617244/docs/release-gate-integration.md)에서 확인할 수 있습니다.

---

## 발견한 크리티컬 리스크

| #  | 리스크                                | 의미                                                                                                                                                 |
| -- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1 | **단순 pass/fail 함정**         | "테스트 다 통과했으니 배포한다"는 판단이**P1 미해결 결함**, **critical area 변경**, **자동화 미커버 영역의 수동 보강 누락**을 놓침 |
| R2 | **암묵적 판단의 재현 불가능성** | 시니어 QA 머릿속의 "이건 좀 위험한데" 감각이 문서·근거로 남지 않음 → 인적 편차로 인한 잘못된 GO 의사결정                                           |
| R3 | **rollback 미비 리스크**        | 모니터링 owner, rollback plan/test 없이 배포 → 사고 발생 시 복구 지연이 임팩트를 키움                                                               |

→ 그래서 릴리즈 판단을 `GO` / `CONDITIONAL_GO` / `NO_GO`로 구조화하고, **점수가 어떻게 나왔는지**까지 함께 출력합니다.

---

## 이 프로젝트가 다루는 질문

릴리즈 직전 QA는 단순히 테스트 통과 여부만 보는 것이 아니라 여러 질문을 함께 판단해야 합니다.

- P1/P2 결함이 남아 있는가?
- 실패한 테스트가 핵심 사용자 흐름에 영향을 주는가?
- 변경 범위가 결제, 인증 같은 critical area에 집중되어 있는가?
- 자동화 커버리지가 낮은 영역은 수동 보강이 되었는가?
- 조건부 배포라면 모니터링과 rollback 기준이 준비되어 있는가?

---

## 테스트 설계

### 판정

| 판정               | 의미                                                             |
| ------------------ | ---------------------------------------------------------------- |
| `GO`             | 현재 기준에서 릴리즈 진행 가능                                   |
| `CONDITIONAL_GO` | 릴리즈는 가능하지만 조건부 승인, 보강 테스트, 강화 모니터링 필요 |
| `NO_GO`          | 핵심 결함 또는 critical 테스트 실패로 릴리즈 보류 필요           |

### 룰 기반 리스크 모델 (설명 가능, AI 미사용)

처음부터 복잡한 AI 판단을 쓰지 않고, **설명 가능한 rule-based 모델**로 구성했습니다.

| 리스크 요소     | 예시                                                                 |
| --------------- | -------------------------------------------------------------------- |
| 미해결 결함     | P1/P2 open defect, 고객 영향, workaround 여부, reopen 여부, 결함 age |
| 테스트 결과     | critical/high 실패, blocked 테스트, flaky warning, manual evidence   |
| 변경 범위       | critical area 변경, 변경 크기, 외부 의존성, data migration 여부      |
| 자동화 커버리지 | 전체 / 핵심 플로우 / 변경 영역 커버리지 부족                         |
| 품질 신호       | smoke / regression / API pass rate, flaky count, blocked count       |
| 릴리즈 준비도   | QA sign-off, 운영 승인, rollback plan/test, 모니터링 owner 준비      |

**예시 점수 계산:**

```
risk_score =
  unresolved_p1 * 40
+ failed_critical_tests * 20
+ critical_area_change * 15
+ low_critical_flow_coverage * 15
```

점수는 100점으로 cap 처리하며, 점수뿐 아니라 **어떤 항목이 위험을 높였는지** 함께 출력합니다.

### 입력 데이터의 구조화

현재 버전은 외부 시스템에 직접 연결하지 않고, 릴리즈 판단에 필요한 파일을 읽어 점수를 계산합니다.

| 파일                              | 정보                                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| `data/release_sample.json`      | 릴리즈 기본 정보, 변경 범위, 자동화 커버리지, 품질 신호, 승인/rollback 준비 상태                |
| `data/defects_sample.csv`       | 미해결/해결 결함 목록, 심각도, 고객 영향, 우회 가능 여부,**결함 age**, QA 검증 여부       |
| `data/test_results_sample.csv`  | smoke/regression/API/visual 테스트 결과,**criticality**, failed/blocked/warning, evidence |
| `data/change_scope_sample.json` | 변경 모듈, feature flag, 외부 의존성, 수동 QA focus note                                        |

**결함 데이터 예시** — 단순히 P1/P2 개수만 보지 않습니다:

```
id,title,severity,status,area,affected_flow,customer_impact,workaround,reopened,age_days,verified_by_qa,linked_test
BUG-101,Payment confirmation intermittently fails,P1,open,payment,checkout,high,false,true,4,false,TC-002
```

**테스트 결과 예시** — 단순 pass/fail보다, 어떤 계층의 어떤 critical flow가 실패했는지 봅니다:

```
id,layer,suite,case_name,area,criticality,status,execution_type,evidence,flaky,failure_reason
TC-002,ui,smoke,checkout_card_payment,payment,critical,failed,automated,screenshot,false,confirmation timeout
```

이 구조는 나중에 Jira, GitHub Actions, Excel 체크리스트, CI 리포트에서 데이터를 가져오는 형태로 확장할 수 있습니다.

### 검증 자동화 (pytest)

판단 로직이 의도대로 동작하는지 자체 회귀:

- P1 미해결 결함이 있으면 → `NO_GO`
- 중간 수준 리스크는 → `CONDITIONAL_GO`
- 낮은 리스크는 → `GO`
- 리스크 점수는 100점을 넘지 않음
- resolved defect는 리스크에 포함하지 않음

---

## CI/CD 연동 (GitHub Actions)

PR을 올리면 게이트가 자동 실행되고, **NO_GO면 빌드가 실패해 머지가 차단**됩니다.
`.github/workflows/gate.yml`:

```yaml
name: QA Release Gate

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  release-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      # The gate's own decision logic is regression-tested before it is trusted
      # to block anything.
      - name: Verify gate logic
        run: pytest -q

      # --strict exits 1 on NO_GO, so the build fails and the merge is blocked.
      - name: Run release gate
        run: python run_gate.py --strict

      # Uploaded even on failure: a NO_GO is exactly when the report is needed.
      - name: Upload gate report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: release-gate-report
          path: reports/release_gate_report.md
          if-no-files-found: error
```

판정을 리포트 문자열 grep 으로 읽지 않고 **종료 코드**로 전달합니다.
리포트 문구가 바뀌어도 CI 가 깨지지 않고, 판정과 빌드 성패가 한 곳에서 결정됩니다.

| 종료 코드 | 의미 |
| --- | --- |
| `0` | `GO` 또는 `CONDITIONAL_GO` — 진행 가능 |
| `1` | `NO_GO` — 릴리즈 보류 (`--strict` 일 때만) |

`--strict` 없이 실행하면 판정과 리포트만 출력하고 종료 코드는 항상 `0` 입니다. 로컬 확인용입니다.

> 이 구성으로 "품질 게이트를 통과해야만 배포된다"는 원칙을 파이프라인에 강제합니다.
> 릴리즈 판단이 사람의 구두 승인이 아니라, 재현 가능한 자동 검증 단계로 남습니다.

---

## 자동화의 비즈니스 임팩트

| 임팩트                                | 어떻게 발생하는가                                                                 |
| ------------------------------------- | --------------------------------------------------------------------------------- |
| **릴리즈 회의 시간 단축**       | "왜 이 릴리즈가 NO_GO인가?"가 구두 설명이 아니라 점수 + 항목별 기여도로 즉시 보임 |
| **QA 결정의 일관성**            | 동일 데이터면 동일 결론 → 인적 편차로 인한 잘못된 GO 의사결정 차단               |
| **감사 가능성**                 | 모든 판단이 데이터와 룰로 남음 → 사후 회고와 감사 대응 가능                      |
| **확장 가능한 의사결정 시스템** | Jira / GitHub Actions / CI XML로 입력만 갈아끼우면 그대로 동작 → 자산화          |

---

## 프로젝트 구조

```
qa-release-gate/
- .github/workflows/
  - gate.yml
- data/
  - release_sample.json
  - defects_sample.csv
  - test_results_sample.csv
  - change_scope_sample.json
- pytest.ini
- gate/
  - data_loader.py
  - risk_model.py
  - release_gate.py
  - report_generator.py
- dashboard/
  - streamlit_app.py
- tests/
  - test_risk_model.py
  - test_release_gate.py
- run_gate.py
```

---

## 빠른 실행

```bash
pip install -r requirements.txt
python run_gate.py                       # reports/release_gate_report.md 생성
python run_gate.py --strict              # NO_GO 면 exit 1 (CI 용)
streamlit run dashboard/streamlit_app.py # 대시보드
pytest -q                                # 판단 로직 검증
```

`python run_gate.py` 예상 출력:

```
Release Gate: NO_GO
Risk Score: 100/100
Report: reports/release_gate_report.md
```

대시보드에서 확인 가능한 항목:

- 릴리즈 판정
- Risk Score
- 주요 리스크 Top 5
- 권장 QA 액션
- 릴리즈 변경 범위
- 미해결 결함
- 테스트 결과

---

## QA 포트폴리오 관점

이 프로젝트는 자동화 스크립트보다 **릴리즈 품질 판단**에 초점을 둡니다.

시니어 QA 관점에서 중요한 것은 *"테스트를 실행했다"* 가 아니라, *"이 릴리즈가 나가도 되는지 어떤 근거로 판단했는가"* 입니다. 이 저장소는 그 판단 기준을 **데이터 → 룰 → 리포트 → 대시보드 → CI** 로 분리해 보여줍니다.

---

## 확장 아이디어

- Jira 또는 GitHub Issues에서 결함 데이터 수집
- CI 테스트 결과 XML/JSON import
- 릴리즈별 리스크 추세 시각화
- LLM을 사용한 릴리즈 요약 초안 생성
- `aiops-sentinel`과 연결해 AI가 작성한 릴리즈 요약의 누락/과장 여부 평가
