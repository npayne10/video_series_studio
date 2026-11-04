# VSCS — Automation Progress / Responsiveness Audit

**Status: Code audit COMPLETE; cross-Automation progress remediation NOT implemented**  
**Date:** 2026-11-04  
**Area:** Story → Automation and associated Story Workspace actions  
**Verified branch:** `phase-20.18.2.3.6.3-local-r2v-provider-evaluation`  
**Operator trigger:** During B.5.22 GUI acceptance, **Planning Proposals** visibly returned 1 Episode and 1 Scene proposal, but the operator saw no running indication before the completion message.

## 1. Confirmed fault and scope

File: `src/vscs/presentation/widgets/automation_story_workspace.py` (`AutomationStoryWorkspaceWidget`).

The handlers listed below invoke their automation service's `.generate(...)` directly from the Qt button callback. No `QProgressDialog`, `QThread`, worker, spinner, task status or elapsed-time UI is installed in these handlers. A sufficiently slow call therefore makes the UI appear idle or unresponsive. Some services might finish quickly; absence of feedback is still a usability and operator cost-control defect.

| Current UI action | Handler | Direct service / observed return | Progress currently? | Code authority of result |
|---|---|---|---|---|
| Planning Proposals… | `_generate_planning_proposals` | Semantic interpret → EpisodeSceneProposalAutomationService.generate | **No** | Proposals only; zero governed plan until reviewed/accepted/compiled |
| Shot Proposals… | `_generate_shot_proposals` | SceneShotProposalAutomationService.generate | **No** | Proposals only; no governed Shot Plan |
| Resolve Assets… | `_resolve_assets` | CanonicalEntityAssetResolutionAutomationService.generate | **No** | Proposed resolution; no new Canon |
| Performance Proposals… | `_generate_performance_proposals` | ActionPerformanceProposalAutomationService.generate | **No** | Reviewable performance proposals |
| Environment Proposals… | `_generate_environment_proposals` | EnvironmentProposalAutomationService.generate | **No** | Reviewable Environment proposals |
| Camera & Lighting Proposals… | `_generate_camera_lighting_proposals` | CameraLightingProposalAutomationService.generate | **No** | Reviewable Camera/Lighting proposals |
| Continuity Proposals… | `_generate_continuity_proposals` | ContinuityProposalAutomationService.generate | **No** | Reviewable Continuity proposals |
| Review Gaps… | `_review_gaps` | Review service call; synchronous, possibly short | **No** | Advisory blockers/warnings; no writes |

**Already addressed separately:** **Analyse Story** in `src/vscs/presentation/widgets/browseable_story_workspace.py` uses a worker, an indeterminate progress dialog and elapsed seconds. Full regression **2,405 tests passed**, and actual UI progress appeared during the B.5.22 operator test. Its worker should be used as a design reference, but do not simply reuse a bare QThread for all services without checking database thread safety.

**Not audited exhaustively yet:** Other app sections (Asset generation, CAP generation, provider validation, reference-image generation, production rendering, package compilation, media assembly, file import/export) may have their own progress behavior. **Do not claim all VSCS automation has the issue solely from the eight handlers above.** They need dedicated code and UI checks.

## 2. Why the previous operator sequence was unsafe

The UI's successful message said:

> Generated 1 Episode proposal(s) and 1 Scene proposal(s). No governed planning authority was created.

This is expected, not a failure. It indicates the proposal stage, not the planning stage. Proceed via **Review Proposals… → Mark Selected Reviewed → Accept Selected / Review & Accept Eligible Set… → Compile Accepted… → inspect Production Planning**. Stop and resolve reported blockers without editing planning JSON. Only start Shot Proposals when the required Episode/Scene authority and source context are confirmed.

## 3. Proposed reusable UI-progress contract (next engineering slice)

Design **one shared automation-operation coordinator** for all long-running Story automation commands, rather than adding separate timers or ad hoc thread classes per button.

### User-visible states

`Idle → Preparing → Running → Completed | Failed | CancelRequested → Cancelled/Completed`

Visible status should show:
1. Exact action name (e.g. `Planning Proposals`), Story ID and source revision.
2. Provider/model **if known from actual service metadata**; otherwise say provider unspecified. Never invent a percentage or ETA.
3. Indeterminate progress and elapsed time, updated every second even while provider is running.
4. The current phase **only when actual stage callbacks are available**; do not simulate semantic/AI stages.
5. Explicit statement on potential charges *before* a paid call, and once-only provider consent per deliberate action.
6. Disable the invoking action while running and reject repeated clicks; preserve other navigation only when thread/data safety allows it.
7. Success: proposal counts, **explicit authority boundary**, next review/compile control and a link/navigation to review.
8. Failure: actionable message, provider diagnostics, no success claim, and a clear safe retry path.
9. Cancellation semantics: only offer a functional Cancel button when the provider operation is genuinely cancellable; otherwise hide it and explain why.

### Engineering constraints

- **Do not** simply place `QApplication.processEvents()` around a synchronous AI/provider call and call it nonblocking. That displays a busy prompt but does not keep the UI responsive.
- Audit `DatabaseManager` connection/thread confinement, project filesystem writes and any Qt-owned dependencies before moving `.generate` operations into a worker. Each worker should own or receive a thread-safe service access strategy. Qt widgets and signals must be updated on the GUI thread.
- Ensure deterministic project/Story/revision snapshot checks before and after the operation; no cross-project stale results or unapproved promotion.
- Reject concurrent expensive calls on the same project/Story where output collisions or extra costs are possible.
- Running tasks need an execution ID, a durable audit event when useful, and a user-visible result even if the window is closed (if the operation truly supports detach/recovery). **Do not claim durable background execution until implemented.**
- Do not migrate production generation to this coordinator until its separate governance/hold rules have been explicitly validated.

## 4. Acceptance matrix for progress remediation

1. Long-running stub provider: progress appears immediately, elapsed seconds increment, Qt remains responsive.
2. Provider error: progress closes, clear error displayed, no misleading success.
3. Repeated click during a running call: only one invocation, no duplicate charge.
4. Fast provider and cached provider: no race leaves dialog hung.
5. Source or project changed while running: stale results rejected safely.
6. No false 0–100% indication; genuinely unknown stages show indeterminate progress.
7. Provider cost disclosure and cancellation semantics correctly reported.
8. Two-stage planning semantic → proposal generation shows accurate stages only if callbacks exist; otherwise a single truthful Running state.
9. No writing to project authority or CAP/Canon merely because an operation completed.
10. Qt integration tests and repeated full-suite run; Ruff/mypy/full pytest clean; operator screenshots of Planning and Shot proposals progress.

## 5. Recommended implementation order

- **P0:** shared progress coordinator design and thread/database contract; Planning Proposals and Shot Proposals migration, operator acceptance.
- **P1:** the other five proposal-generation actions and Resolve Assets; guard against duplicate invocations.
- **P2:** Review Gaps and remaining automation actions, only if execution latency warrants it.
- **P3:** global audit of all VSCS long-running actions (CAP/reference generation, provider validation, rendering/ComfyUI, exports), with a unified visual convention and truthful cancel/retry behavior.

The progress work should receive its own versioned phase/acceptance record rather than being silently mixed into B.5.22's disk-backed CAP persistence acceptance.

## 6. Current acceptance evidence and operator recommendation

**B.5.22 current GUI state:** `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`, Story `STORY-001` Approved, Story Analysis completed and progress observed, **1 Episode + 1 Scene proposal generated**. The next verified control is **Review Proposals…**. Do **not** regenerate Planning Proposals merely to see whether it is busy; that may incur an extra provider call. Do not treat the absence of a running indicator as a failed generation when the success message is present.

No application code changes have been made to the other seven Automation handlers as part of this audit document.

## 7. First implementation slice — 2026-11-04 (NOT YET ACCEPTED)

The operator authorised a common progress system before generating B.5.22 Shot proposals. A shared `AutomationProgressRunner` has been committed in `src/vscs/presentation/widgets/automation_progress.py`, integrated with `AutomationStoryWorkspaceWidget._generate_planning_proposals` and `_generate_shot_proposals`.

- These two actions no longer invoke their provider-bound proposal operation on the Qt GUI event loop. Their existing service calls and human proposal/compilation authority boundaries are unchanged.
- Both show an indeterminate modal **Planning Proposals — Running** or **Shot Proposals — Running** window with Story ID and elapsed seconds, and no false completion percentage.
- The dialog has no misleading Cancel action (the provider call is not safely interruptible); duplicate-run attempts on the same runner are rejected. No user navigation to another project can normally occur while modal progress is open.
- Qt tests in `tests/test_story_automation_progress.py` cover progress visibility and worker-thread execution, fast completion, provider exception and duplicate-call guard. **Operator must run tests; not yet verified.**
- **Caveat:** the wrapper uses a worker thread and the two migrated services' file-backed proposal generation. This is **not** an automatic safety endorsement for additional automation handlers that may touch thread-confined SQLite connections; evaluate separately before extending.
- Provider/model details and genuine stage callbacks are not yet surfaced by this first slice. Future shared runner improvements must use actual service metadata only, not invented model/stage progress.
- Existing Story Analysis progress remains its previously accepted implementation; further consolidation of both implementations is a distinct engineering task.

**Revised audit statuses**: Planning Proposals and Shot Proposals = **implemented, unverified**. The other five proposal generation actions, asset resolution and Review Gaps remain **progress missing / code audit**. No global “all Automation tasks fixed” claim is justified.
