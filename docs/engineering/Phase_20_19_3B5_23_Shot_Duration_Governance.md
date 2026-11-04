# Phase 20.19.3B.5.23 — Shot Proposal Duration Governance

**Status:** Implementation committed; Windows tests, full regression and operator acceptance pending  
**Date:** 2026-11-04  
**Origin:** B.5.22 disposable desktop acceptance, `STORY-001`, Ready Scene `EP-001-SCN-001` with **35-second** duration.

## Defect

The approved Episode and Scene were compiled successfully at 35 seconds. The existing AI Shot Proposal provider generated only **one 35-second Shot** (`EP-001-SCN-001-SHT-001`). The previous `SceneShotProposalAutomationService._fit_runtime_budget` and `_validate_runtime_budget` only protected upper total Scene runtime and positive Shots, **not** the approved VSCS production-generation target of 15–20 seconds per Shot. This would have allowed human approval/compilation of a generation-incompatible Shot. No Shot was accepted or compiled in the operator project.

## In-place implementation

Existing source: `src/vscs/application/automation/scene_shot.py`.

The existing service now applies `_enforce_shot_duration_policy` **after** provider output/budget fitting and **before** any proposal is persisted:
- Every proposed Shot must have **15–20 seconds**. A Scene with 35 seconds and a single 35-second provider Shot becomes **18 + 17 seconds**, with deterministic contiguous Shot sequence numbers, equal total Scene duration and original Story/Scene provenance. All resulting Shots stay **Proposed**, with no governed Shot Plan or provider submission.
- Oversized provider Shots are split only if the duration can be partitioned into compliant segments. The original one-time action, narrative purpose, dialogue and event-bearing constraints are retained by the **first** segment. Later segments explicitly **hold the prior end state without replay**, preserving continuing static visual constraints such as no personnel/camera movement. The provider's original continuity-in is retained on the first segment; original continuity-out on the final segment.
- Exactly-one occurrence of the indicator pulse across segments is **proposed**, not guaranteed by video generation; human review and later media validation must inspect that the pulse occurs once.
- The provider's output must cover the Scene's total time exactly; under-budget or unpartitionable provider results raise a descriptive error before any Shot proposals from that Scene are saved. This change intentionally tightens old permissive semantics and may require older tests expecting short/incomplete Shots to be updated to distinguish historical behavior from the new policy.
- The source Story, Scene status, Episode status, original unaccepted proposal in the disposable project, CAP, Canon and Production Approval are unchanged by the code commit. **Do not regenerate proposals before validation.**
- The 15–20 second limits are class constants for this phase. Centralised configuration and provider pre-prompting are potential subsequent improvements, not claimed implemented here.

## Acceptance tests committed

`tests/test_phase_20_19_3b5_23_shot_duration_policy.py` covers:
- Scene durations 15, 20, 35, 40 and 45 seconds, exact runtime budgets and deterministic sequence.
- Single pulse only in first Shot, no replay in subsequent segments.
- Impossible 1, 14, 21, 22, 29, 41 and 44 second inputs must fail clearly.
- Provider output that underfills a Scene fails rather than truncating/pretending completion.
- End-to-end proposal-service call creates two **Proposed** Shots, retains parent Scene provenance and does not create governed authority.
- Impossible generation fails before saving any proposal.

**Potential existing regression impact:** Previous tests may have exercised durations outside the new 15–20-second policy; run all acceptance checks and resolve test/design inconsistencies in GitHub (do not locally patch test fixtures to conceal a genuine policy conflict).

## Operator steps: tests

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_23_shot_duration_policy.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## Actual GUI acceptance only after full green tests

1. Reopen disposable `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` and confirm `STORY-001` Approved, Episode/Scene Ready, original 35-second Shot proposal still **Proposed**.
2. Deliberately rerun **Story → Automation → Shot Proposals** once to replace the *unaccepted* original Shot suggestion with policy-compliant proposals. Do **not** rerun Planning Proposals.
3. Verify progress window and completion summary say **2 Shot proposals for 1 Scene**.
4. In **Proposal Review**, inspect `EP-001-SCN-001-SHT-001` and `...SHT-002`: runtimes **18 + 17**, sequence 1/2, a single pulse event only in first Shot, second Shot continuation (no repeated pulse), same Story revision, and neither is Accepted/compiled.
5. Review both with a human reviewer; only accept and compile once narrative and status are verified. Confirm actual governed Shot plans and all subsequent asset binding/CAP gates separately.
6. If any tests or UI output disagree, stop rather than promoting an invalid Shot.

The user-maintained untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` remains untouched; pre-existing `B5_19A_ACCEPTANCE` is not used.
