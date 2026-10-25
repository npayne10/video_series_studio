# Phase 20.19.3 — Controlled Story-to-ProductionTask Golden Path

**Status:** Initiated. Scope validator committed; operator-native project creation and story-to-task execution pending. No H3 live-generation authorization.

## Scope and project isolation

Create a NEW native VSCS project by **File → New Project**:

- Parent folder: `D:\VSCS\GOLDEN_PATH_AUDIT\RUN-001`
- Project name: `Episode Audit`
- Expected project file: `D:\VSCS\GOLDEN_PATH_AUDIT\RUN-001\Episode Audit\project.vscs`

Do not use the existing H3 project (`D:\VSCS\H3_ACCEPTANCE\Q3_1_3_5_8\RUN-001`), production TSR2 (`D:\VSCS TSR2`), or any TSR2-derived test project. Native New Project may create its own project-named subfolder; inspect the actual path instead of fabricating a metadata file. Run the scope validation only after native creation. The validator never writes anything or invokes a provider.

## Synthetic story test content

**Title:** `The Quiet Console — Episode Audit`  
**Source type:** Original  
**Description:** `Disposable VSCS episode-production workflow trace with one static shot.`  
**Genre:** `Science Fiction`  
**Synopsis:** `A silent engineering console on an empty exploration vessel briefly reports a routine diagnostic change. The environment remains stable and nobody enters.`  
**Theme:** `Observation, consistency`  
**Audience:** `Adult science-fiction viewers`  
**Language:** English  
**Target runtime:** Story estimate can remain unestimated. The episode planner enforces a minimum episode runtime of **60 seconds**, even though our single-shot acceptance sample will be short.

No existing Xorix or TSR2 material may be imported. The first trace should exercise **New Story**. A second, separately controlled variant can exercise **Import Story** with an actual synthetic text file; parser behavior must not be presumed from Source Type labels.

## Native operator trace and evidence

| Gate | UI operation | Required proof | Stop condition |
|---|---|---|---|
| GP-00 | Create project via File → New Project | Native `project.vscs` and database | Existing/non-disposable path |
| GP-01 | Story → Workspace → New Story | Persisted Story ID, status, source metadata | Creation/validation error |
| GP-02 | Story Analysis, review, mark analysed, approve as appropriate | Story analysis revision and real approval evidence | Approval cannot be legitimately reached |
| GP-03 | Story → Production Planning (currently silent without selected Story) | Episode Planner opens for selected eligible Story | Button still disabled; log UI-035 exact state |
| GP-04 | Episode Planner → New Episode | Episode ID, title, scope, objective; required runtime >=60 s | Missing episode authority |
| GP-05 | Episode Planner → Scene Planner → Shot Planner | Native episode, scene, shot IDs and one-shot relationship | UI cannot create governed shot |
| GP-06 | Assets, Canonical Profiles, Behaviour Profiles | One synthetic asset with genuinely approved reference as required by policy | Reference cannot be approved |
| GP-07 | Top-level Production Planning tabs | Action, assets, temporal presence, camera, lighting, continuity, universal description persisted | Missing or stale authority |
| GP-08 | Production Review | Validation passes; human reviewer approves in UI | Missing reviewer or unresolved errors |
| GP-09 | Production Tasks → Compile Production Tasks | Exactly one native task and PLANNED state; IDs, revision and fingerprints captured | Task absent/invalid |
| GP-10 | Readiness inspection **only** | Readiness status and blockers, no provider execution | Any tool attempts external submission |

**Stop at GP-09/10.** No schedule approval, queue compilation, H3 live run or generated media is needed for this phase.

## Help-register evidence

For each form: record full dropdown choice set, field label/object name, required/optional state, defaults, accepted examples, validation messages, state-dependent enablement, and exact next-step guidance. Add discoveries to `docs/engineering/Phase_20_19_Field_Help_Examples_Controlled_Choices_Register.md`. Do not guess finite enums from a single selected value.

## Read-only CLI after native project creation

```powershell
python -m vscs.infrastructure.production_execution.golden_path_scope `
  --audit-project "D:\VSCS\GOLDEN_PATH_AUDIT\RUN-001\Episode Audit" `
  --h3-acceptance-root "D:\VSCS\H3_ACCEPTANCE\Q3_1_3_5_8\RUN-001" `
  --protect "D:\VSCS TSR2"
```

Expected `ISOLATED_NATIVE_PROJECT_READY_FOR_UI_TRACE`. The status guarantees only project isolation and the reported H3 hold state, **not** that any Story has been approved or task created.

## Approval and regression rules

- Only user-authorized UI lifecycle operations may mutate the new audit project.
- No fake JSON, no direct SQLite mutations, no synthetic approval fingerprints.
- No changing live H3 hold or shared providers; no other projects edited.
- Focused tests, Ruff, mypy, full pytest and explicit UI evidence required before marking each development milestone complete.
- Phase 20.19.4 approved UI restructuring remains **deferred** until this golden-path diagnostic completes.
