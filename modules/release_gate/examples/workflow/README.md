# Synthetic Baseline/Target → release gate demo

This is an offline contract demonstration written for the public
[AI QA Workflow Platform](https://github.com/tempesty-ai/ai-qa-workflow-platform).
All IDs, SHAs, evidence references, reviews and approvals are fictional. References beginning with
`synthetic://` are labels; no service or company system is contacted.

Read the [proposed policy](../../docs/workflow-quality-gate-policy.md) before interpreting a decision.
Use Python 3.11+ from the repository root; the new evaluator uses only the standard library.

```bash
python run_workflow_gate.py --input examples/workflow/go.json --policy examples/workflow/policy.json --as-of 2026-10-16T00:00:00Z --strict --output-dir reports/workflow/go
```

Repeat with the other fixture names and different output directories:

| Input | Evidence | Risk score | Decision | Strict exit |
| --- | --- | --- | --- | --- |
| `go.json` | COMPLETE | 0 | GO | 0 |
| `conditional_go.json` | COMPLETE | 15 (one P2) | CONDITIONAL_GO | 3 |
| `no_go.json` | COMPLETE | null (hard blocker) | NO_GO | 1 |
| `evidence_insufficient.json` | INSUFFICIENT | null (not assessed) | EVIDENCE_INSUFFICIENT | 2 |

Each run writes `result.json` and `report.md`. Nonzero strict exits are intentional for the last three
examples. Omit `--strict` for interactive report exploration. Omit `--as-of` to use the current UTC
clock; old fixed fixtures will then age out as designed.

## Public export contract v1

The complete, machine-readable examples above are the canonical contract fixtures. The evaluator
validates exact fields and types; see `validate_contract` in `gate/workflow_policy.py`.

| Field | Meaning |
| --- | --- |
| `schema_version`, `synthetic` | Exactly integer `1` and boolean `true`; real operational exports are unsupported |
| `release` | `id`, 40-character lowercase `candidate_sha`, `environment` |
| `scope` | Nonempty declared Baseline and Target cases: unique `case_id`, `suite` (`baseline`/`target`), `criticality` (`critical`/`high`/`medium`/`low`) |
| `results` | One explicitly selected run per scoped case, bound to candidate/environment |
| Result fields | `case_id`, `candidate_sha`, `environment`, `observed_at`, `status`, `failure_kind`, boolean `flaky`, `review`, list `evidence_refs` |
| Result status | `passed` / `failed` / `blocked` / `error` / `not_run` |
| Failure kind | `none` for passed; `product` / `automation` / `environment` / `unknown` for others |
| Review | `approved` / `pending` / `rejected`; automation pass never implies review approval |
| `defects` | Explicit list (may be empty): unique `id`, `severity` (`P1`/`P2`/`P3`), `status` (`open`/`resolved`) |
| `readiness` | Boolean `qa_signoff`, `operations_approval`, `rollback_tested`; string `monitoring_owner`, `rollback_trigger` |
| `conditional_acceptance` | `null`, or string `approved_by`, `mitigation`, timezone-aware `expires_at` |

An eventual authorized exporter would need to resolve candidate identity, select runs without hiding
failures, carry manual review separately, and verify artifact integrity. This repository adds no
connection to the private platform. The public demonstration is independently authored from this
contract and synthetic data only.

## Regression verification

```bash
python -m pip install pytest
python -m pytest -q
```

Tests exercise inclusive threshold/freshness boundaries, score cap/configuration, hard-blocker
precedence, missing and malformed evidence, duplicate/out-of-scope runs, wrong candidate/environment,
stale/future timestamps, unreviewed runs, infrastructure/automation errors, missing readiness,
conditional acceptance/expiry, all CLI exits/reports, and the unchanged legacy regression tests.

The [demo CI workflow](../../.github/workflows/workflow-evidence-demo.yml) asserts all four expected
exit codes and uploads their reports even if a scenario regresses.
