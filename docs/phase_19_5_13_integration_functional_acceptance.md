# Phase 19.5.13 — Integration & Functional Acceptance

Phase 19.5.13 is the closure gate for Phase 19. It adds no new production authority. It evaluates whether the current Story revision has sufficient, coherent and human-governed Phase 19 evidence to proceed beyond Story-to-Production Planning automation.

## Acceptance matrix

| Area | Acceptance rule | Automated result |
| --- | --- | --- |
| Current revision | Phase 19 proposals exist for the selected Story revision | PASS / FAIL |
| Structure | Episode, Scene and Shot proposals all exist | PASS / FAIL |
| Production specialists | Action/Performance, Environment, Camera, Lighting and Continuity proposals exist | PASS / REVIEW |
| Per-Shot specialist coverage | Every Shot has all five specialist proposal types | PASS / REVIEW |
| Provenance | Every evaluated proposal belongs to the selected Story and source revision | PASS / FAIL |
| Human governance | Accepted or rejected proposals retain explicit human identity | PASS / FAIL |
| Canonical governance | Every detected entity is resolved to XPD or explicitly scoped as Prompt Element / Scene Continuity | PASS / REVIEW |
| Approval boundary | Automation proposals never contain final Production Approval markers | PASS / FAIL |
| Persistence | Acceptance evidence produces the same report after project close/reopen | automated integration test |
| UI access | Functional acceptance is available from Story hierarchical navigation | automated integration test |

## Functional acceptance workflow

1. Open the project and select the Story.
2. Complete Story Analysis and Phase 19.5 proposal generation.
3. Review and accept eligible proposals where appropriate.
4. Import/reuse canonical XPD authority and complete canonical-scope review.
5. Bind canonical Shot assets.
6. Open **Story → Integration & Functional Acceptance…**.
7. Resolve every FAIL criterion.
8. Review every REVIEW criterion and complete the remaining human decision.
9. Re-run the report until all criteria are PASS.

The report is read-only. Running acceptance does not accept proposals, mutate governed Episode/Scene/Shot plans, create XPD/CAP authority, mark anything Ready, submit to a provider, or perform Production Approval.

## Manual functional acceptance — The Silent Relay

The representative Phase 19 acceptance Story is **The Silent Relay** in the VSCS TSR project. Confirm that governed Production Planning contains the accepted Episode, all Scenes and all Shots; that proposal evidence exists for Action/Performance, Environment, Camera, Lighting and Continuity; that canonical identities are either resolved or explicitly scoped outside global XPD; that the XPD review dialog and functional acceptance dialog can be closed and reopened normally; and that restarting/reopening the project preserves the same proposal/governance state.

Phase 19 may be closed only when the full automated regression suite passes and the current Story revision has no FAIL or REVIEW entries in the functional acceptance report, except where a REVIEW item is explicitly documented as a deliberate deferred human decision that blocks downstream production.
