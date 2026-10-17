# Workflow quality gate — proposal v1

**Status: proposed defaults for a synthetic integration demo, not a universal quality standard.**
The thresholds have not been calibrated against production incidents. Adopt or change them only after
reviewing the product's failure cost, critical journeys, release history and recovery capability.
This document specifies `gate/workflow_policy.py`; it does not redefine the legacy CSV gate.

## Two independent questions

1. **Evidence completeness:** do we have current, reviewed results for every case in the declared
   Baseline and Target scope, for this candidate and environment?
2. **Release risk:** given sufficient evidence, what confirmed defects, product failures and flaky
   signals remain, and are release controls ready?

Missing evidence is unknown risk, never zero risk. A passing automation result and an approved human
review are separate fields. Environment/automation failures do not become product defects or passes.
Every expected case must be declared before evaluating; this prototype cannot discover omitted scope.

| Evidence status | Release facts | Decision |
| --- | --- | --- |
| Invalid contract | Facts cannot be interpreted reliably | `EVIDENCE_INSUFFICIENT` |
| Complete or insufficient | Current confirmed critical product failure, open P1, or missing release readiness | `NO_GO` |
| Insufficient | No established hard blocker | `EVIDENCE_INSUFFICIENT` |
| Complete | Score ≥ 45 | `NO_GO` |
| Complete | Score 20–44, or any open P2 / noncritical product failure / flaky result | `CONDITIONAL_GO` only with valid acceptance; otherwise `NO_GO` |
| Complete | Score < 20 and no condition above | `GO` |

Hard blockers take precedence over evidence gaps **only after the input is structurally valid**.
Both axes are always reported, so `NO_GO` can coexist with insufficient evidence. Scores are `null`
when evidence is insufficient or a hard blocker stops scoring, rather than misleadingly reporting 0.

## Evidence admission (100% of the declared scope)

The demo requires at least one Baseline case and one Target case. Each scoped case must have exactly
one selected result; duplicate, unknown and out-of-scope case IDs are rejected. Rerun selection must
be explicit upstream; the evaluator never chooses the most favorable attempt.

Each result must meet all of these conditions:

- Candidate SHA and environment exactly match the release.
- Timestamp includes a timezone. Age is at most **24 hours**, inclusive; a future offset up to
  **5 minutes**, inclusive, tolerates clock skew. These are configurable proposals.
- Human review is `approved`, and at least one nonempty evidence reference is present.
- Status is `passed`, or `failed` with `failure_kind=product`.

`blocked`, `not_run`, `error`, and failures classified as automation/environment/unknown leave evidence
insufficient. Pending/rejected review, absent results/references, stale or wrong-candidate evidence
also leave evidence insufficient. An empty test list cannot pass. Unrecognized enum values, wrong
types (including string booleans), duplicate JSON keys and unknown fields are rejected.

References are **opaque synthetic handles**; the demo does not fetch files, verify reference content,
authenticate reviewers or prove completeness of an upstream export. A timestamp and input hash are
traceability aids, not signatures or proof of test correctness. CI passing a synthetic scenario does
not demonstrate product quality or authorize a real deployment.

## Hard blockers and release controls

- Any **open P1** defect blocks; resolved defects add no risk.
- A `critical` case with a **confirmed product failure** blocks when its result is current,
  candidate/environment-bound, reviewed and evidenced. A stale or unreviewed failure requires evidence
  repair; it cannot establish a current confirmed failure.
- `qa_signoff`, `operations_approval`, `rollback_tested` must all be true; `monitoring_owner` and
  `rollback_trigger` must be nonempty. Known missing controls mean `NO_GO`, not missing evidence.

These blockers and the 100% admission requirement are deliberately mandatory in v1. Score tuning
cannot waive them. Changing them requires a reviewed policy/code revision, not a CLI override.

## Proposed residual risk score

| Confirmed signal | Default points | Additional rule |
| --- | --- | --- |
| Open P2 | 15 each | At least conditional |
| Open P3 | 5 each | Score based |
| High / medium / low product test failure | 12 / 6 / 3 each | At least conditional |
| Flaky selected result, including a passing retry | 5 each | At least conditional |

Sum contributions and cap at 100. This is a prioritization score, **not a probability, coverage
percentage or estimate of financial loss**. There is no pass-rate denominator to dilute a critical
failure by adding easy passing tests. A product failure and an associated defect can both contribute;
v1 conservatively counts both and does not pretend to deduplicate their underlying cause.
Change size, migration safety, security and operational telemetry are not modeled here; teams must
add reviewed checks before treating this as a production gate. Criticality and defect severity are
trusted declared inputs and require governance outside this demo.

The default boundary of 20 permits a small documented P3 backlog but makes four such issues conditional;
45 rejects a larger accumulated backlog. These choices make the demo explainable, not empirically
validated. Open P2s, product failures and flaky runs cannot receive GO even when below 20.

For conditional release, require a named approver, mitigation, and a timezone-aware acceptance expiry
strictly later than evaluation time, in addition to all readiness controls. A missing/blank/expired
acceptance yields `NO_GO`. The JSON is a synthetic representation of acceptance, not an authenticated
approval mechanism. Re-evaluate immediately before any real release; do not reuse an old decision.

## Configuration and reproducibility

[`examples/workflow/policy.json`](../examples/workflow/policy.json) lists the resolved defaults.
`--policy custom.json` may override a subset of the numeric fields; unknown fields are errors.
Require integer `0 < conditional_min < no_go_min <= 100`, positive integer weights, finite
`0 < max_age_hours <= 8760` and `0 <= future_tolerance_minutes <= 60`.
The upper age bound is a validation guard, not a recommended evidence lifetime.

Every JSON/Markdown report records policy ID, resolved policy, evaluation time, input SHA-256,
evidence gaps, blockers and every score contribution. The fixed fixture clock is
`2026-10-16T00:00:00Z`. `--as-of` is only for replaying synthetic fixtures; omit it when evaluating
fresh inputs. Offline local replay cannot authenticate a clock or input provenance.

## Compatibility and exit codes

`run_gate.py`, `gate/release_gate.py`, the dashboard, legacy CSV inputs and legacy exit codes remain
unchanged. In particular, the legacy policy treats blocked critical tests as NO_GO, whereas this
proposal classifies unexecuted/unconfirmed results as insufficient evidence. Do not silently mix
these policies or present legacy 45/80 thresholds as this policy's 20/45 defaults.

The new, opt-in entry point is `run_workflow_gate.py`:

| Strict exit | Meaning | CI action |
| --- | --- | --- |
| 0 | GO | Recommendation permits proceeding |
| 1 | NO_GO | Hold |
| 2 | EVIDENCE_INSUFFICIENT | Hold; repair evidence |
| 3 | CONDITIONAL_GO | Manual hold, even with recorded acceptance |
| 4 | Invalid policy or evaluation-time configuration | Fix configuration |

Without `--strict`, all reported decisions exit 0 for exploration; invalid configuration still exits 4.
Malformed/missing input produces an insufficient-evidence report. A filesystem write failure remains
a process error, never a successful decision. A real pipeline must consume strict exits and configure
required status checks / approval controls separately; creating this demo does not configure them.

The existing `QA Release Gate` workflow still runs its intentionally NO_GO legacy fixture with
`--strict` and therefore fails. That existing behavior is preserved. The new `Workflow Evidence Demo`
workflow asserts expected fixture outcomes and passes when the evaluator behaves correctly; its
success is a regression-test result, not a release authorization.

## Reproduce and connect the repositories

See the [executable demo](../examples/workflow/README.md) for all four outcomes and the
[public platform documentation](https://github.com/tempesty-ai/ai-qa-workflow-platform).
The platform's proposed companion PR supplies an independent synthetic export and a GitHub Actions
consumer pinned to the gate implementation commit. No company source, operational results, DB schema,
credentials, production connectors or original test runners are required or copied.
