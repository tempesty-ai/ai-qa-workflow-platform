# TMS 안으로 통합한 릴리즈 게이트

현재 실행 진입점은 저장소 루트의 `python -m tms demo`입니다.
[TMS 실행 안내](../README.md) · [구조와 계약](tms-architecture.md) · [결함 심각도 기준](severity-policy.md)

기존에는 플랫폼 문서 저장소의 고정 JSON을 외부 게이트 저장소의 고정 커밋으로 평가했습니다.
이제 기존 공개 게이트를 [`modules/release_gate/`](../modules/release_gate/UPSTREAM.md)에 통합하고,
TC 실행 → 실제 합성 증적 → 별도 검수 → 영향 분류 → 게이트 판정을 한 저장소에서 재현합니다.
외부 저장소를 추가 clone/checkout할 필요가 없습니다.

기존 코드와 JSON·CSV 입력, 판정과 종료 코드는 보존합니다. TMS의 제안 S1/S2/S3 분류만 별도 계층에서 수행하고
게이트의 기존 P1/P2/P3 계약으로 변환합니다. 근거가 부족한 결함은 낮은 등급으로 추정하지 않습니다.

## 이전 공개 JSON을 그대로 재생

```bash
python modules/release_gate/run_workflow_gate.py --input demo/release-gate/synthetic-evidence.json --policy modules/release_gate/examples/workflow/policy.json --as-of 2026-10-16T00:00:00Z --strict --output-dir reports/previous-contract
```

예상 결과는 이전과 같은 CONDITIONAL_GO / 15점 / 종료 코드 3입니다.
새 TMS의 conditional 실행은 실제 필터 실패와 S2를 함께 평가하므로 27점입니다. 서로 다른 시나리오이며 기존 결과를 바꾼 것이 아닙니다.
`--as-of`는 고정 과거 fixture 재생 전용입니다. 새 TMS 실행은 현재 UTC 시각을 기록합니다.

루트 [TMS Integration CI](../.github/workflows/release-gate-demo.yml)는 통합 실행과 이전 JSON/CSV의 기대 판정을 모두 검사합니다.
예상 NO_GO / exit 1을 검증 성공으로 다루므로 정상적인 보류 시나리오가 CI 장애 알림으로 표시되지 않습니다.
별도 qa-release-gate 리포의 기존 CI는 이번 변경 범위가 아닙니다.

[통합 이전의 연동 기록](archive/release-gate-integration-2026-10-16.md)은 별도 보관했습니다.
회사 원본 플랫폼 코드·실제 서비스 연결을 가져오지 않았고, 공개 게이트와 독립 작성한 합성 TMS 데모만 통합했습니다.
