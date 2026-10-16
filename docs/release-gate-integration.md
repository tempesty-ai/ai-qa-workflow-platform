# Baseline·Target 결과를 릴리즈 판단으로 연결하는 공개 데모

**구현 범위: 합성 JSON → 공개 게이트 엔진 → 판정·근거 보고서 → GitHub Actions artifact.**
회사 플랫폼과 운영 시스템을 직접 연결한 구현이 아닙니다. 이 문서 저장소의 원본 서버·DB·실행기·검수
코드를 복사하지 않고, 공개 가능한 개념을 바탕으로 입력 계약과 가상 데이터를 새로 만들었습니다.

## 두 가지 질문을 분리합니다

1. **증거가 충분한가?** 선언한 Baseline·Target 범위의 모든 결과가 현재 후보 버전·환경에 해당하며,
   최신이고, 증적 참조와 사람의 검수 승인이 있는지 확인합니다.
2. **출시 위험을 감수할 수 있는가?** 확인된 결함·제품 실패·불안정 신호와 승인·복구 준비를 평가합니다.

자동 판정 PASS가 사람의 검수 완료를 뜻하지 않습니다. 환경 오류나 미실행을 제품 실패 또는 성공으로
바꾸지 않고 증거 부족으로 남깁니다. 모르는 위험을 0점으로 표시하지 않습니다.

| 상태 | 제안 기준 | 다음 행동 |
| --- | --- | --- |
| `GO` | 증거 충분, 필수 준비 완료, 점수 < 20, 별도 조건부 신호 없음 | 현재 정책 내 진행 권고 |
| `CONDITIONAL_GO` | 증거 충분, 20–44점 또는 P2·비핵심 제품 실패·flaky, 유효한 조건부 수용 기록 있음 | 담당자의 추가 판단·조건 확인; CI 자동 통과 금지 |
| `NO_GO` | P1·확인된 핵심 제품 실패·필수 승인/복구 준비 미완료·45점 이상·필요한 조건부 수용 누락 | 보류 사유를 해소한 뒤 재평가 |
| `EVIDENCE_INSUFFICIENT` | 입력 오류·누락·미검수·잘못된 버전·오래된 증거·실행 장애 등 | 증거 보완 후 재평가 |

구조가 유효한 입력에서 확인된 hard blocker는 다른 증거 부족보다 우선하며, 보고서에는 두 축을 모두 남깁니다.
점수는 확률이 아닙니다. **20/45점, 유효기간 24시간, 미래 시각 오차 5분은 보수적으로 선택한 제안**이며,
운영 사고 데이터로 검증한 보편적 기준이 아닙니다. 제품 영향·복구 비용·배포 이력으로 조정해야 합니다.
점수 경계·가중치·증거 유효기간은 설정 가능하지만, 필수 준비와 중대 결함 조건은 점수로 면제할 수 없습니다.

정확한 경계·가중치·우선순위·정책 한계는 [게이트 정책 원문](https://github.com/tempesty-ai/qa-release-gate/blob/8cf46ab48eef79fc939b2212e51bc90e23df3450/docs/workflow-quality-gate-policy.md)에 명시했습니다.

## 공개 개념과 입력 계약의 대응

| 플랫폼에서 설명한 개념 | 공개 데모 필드 | 의미와 한계 |
| --- | --- | --- |
| Baseline·Target 검증 범위 | `scope[].suite`, `case_id`, `criticality` | 사전에 선언한 범위; 누락된 범위를 스스로 발견하지 못함 |
| 제품 버전·실행 조건 | `release.candidate_sha`, `environment`, 결과별 동일 필드 | 후보 버전/환경이 다르면 사용할 수 없음 |
| 코드의 자동 판정 | `results[].status`, `failure_kind`, `flaky` | 제품 실패와 자동화/환경 문제 구분 |
| 증적과 검수 | `evidence_refs`, `review`, `observed_at` | 승인·참조·최신성 확인; 실제 파일/검수자 인증은 수행하지 않음 |
| 미해결 결함 | `defects` | P1/P2/P3와 open/resolved의 명시적 합성 목록 |
| 출시 준비·조건부 수용 | `readiness`, `conditional_acceptance` | 담당자·보강 조치·만료 시각, 승인·모니터링·rollback 준비 |

현재 게이트는 Baseline과 Target이 각각 하나 이상인 릴리즈만 다룹니다. 모든 선언 TC에 결과가 있어야 합니다.
재실행 기록 중 어떤 결과를 사용할지는 내보내는 쪽에서 명시해야 하며, 중복·범위 밖 결과는 거절합니다.
실제 exporter나 사내 API/DB adapter는 구현하지 않았습니다.

## 이 저장소에서 재현하기

[`synthetic-evidence.json`](../demo/release-gate/synthetic-evidence.json)은 가상 Baseline 1건·Target 1건,
P2 1건과 가상 조건부 수용 기록을 담습니다. 후보 SHA, 담당자, 승인, 증적은 전부 예시입니다.
실제 테스트 실행·사람 검수·제품 품질을 입증하는 파일이 아닙니다.

이 저장소 루트에서 Python 3.11+로 실행합니다. 별도 패키지나 인증정보는 필요하지 않습니다.

```bash
git clone https://github.com/tempesty-ai/qa-release-gate.git ../qa-release-gate
git -C ../qa-release-gate checkout 8cf46ab48eef79fc939b2212e51bc90e23df3450
python ../qa-release-gate/run_workflow_gate.py --input demo/release-gate/synthetic-evidence.json --policy ../qa-release-gate/examples/workflow/policy.json --as-of 2026-10-16T00:00:00Z --strict --output-dir reports/release-gate-demo
```

예상 출력은 `CONDITIONAL_GO | evidence=COMPLETE | risk=15`, 종료 코드는 **3(수동 보류)** 입니다.
`reports/release-gate-demo/result.json`과 `report.md`에서 정책·평가 시각·입력 해시·근거·조건을 확인합니다.
`--strict`를 빼면 탐색용으로 보고서를 만들고 0으로 종료합니다. `--as-of`는 고정 데모 재생용입니다.
현재 시각으로 평가하려면 이 옵션을 생략하며, 이 고정 샘플은 시간이 지나면 의도대로 오래된 증거가 됩니다.

[다른 세 판정의 입력과 실행법](https://github.com/tempesty-ai/qa-release-gate/blob/8cf46ab48eef79fc939b2212e51bc90e23df3450/examples/workflow/README.md)도 공개되어 있습니다.
기존 `run_gate.py`·CSV·대시보드와 기존 45/80점 정책은 이 새 정책과 별도로 유지됩니다.

## GitHub 연결과 검증 범위

[`Synthetic Release Gate Integration`](../.github/workflows/release-gate-demo.yml)은 PR·main push·수동 실행 시
이 저장소의 합성 JSON을 고정 게이트 커밋 **`8cf46ab48eef79fc939b2212e51bc90e23df3450`** 으로 평가합니다.
그 후 예상 판정·점수·종료 코드 3을 확인하고 보고서를 artifact로 보관합니다.
토큰 전달, 회사 API, DB, 외부 증적 조회, 배포, 이슈 댓글 게시를 하지 않습니다.

워크플로가 초록색인 것은 **이 합성 시나리오가 예상대로 조건부 보류되었다**는 뜻입니다.
실제 출시 허용 또는 기존 플랫폼의 전체 테스트 통과를 뜻하지 않습니다. 실제 배포 연결에는 입력의
진위·범위·증적 내용과 검수자 인증, 현재 시각 재평가, required check와 사람 승인 구성이 별도로 필요합니다.

게이트 저장소 테스트는 점수 경계·hard blocker·증거 부족·만료·버전 불일치·실행 장애·조건부 수용과
기존 동작을 검증합니다. 이 저장소의 워크플로는 **공개 계약의 소비 경로**만 검증하며, README의
2026-10-08 원본 플랫폼 검사와 2026-10-13 촬영 검사 재실행을 주장하지 않습니다.
