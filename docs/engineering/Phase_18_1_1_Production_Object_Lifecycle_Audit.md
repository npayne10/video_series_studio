# Phase 18.1.1 — Production Object Lifecycle Audit

**Document ID:** VSCS-ENG-18.1.1  
**Version:** 1.0  
**Status:** Repository Audit and Implementation Baseline  
**Parent Phase:** 18.1 — Production Object and Workspace Completion  
**Priority:** P0 — Production Critical  
**Reference Production:** Xorix  

## 1. Purpose

This audit establishes the actual lifecycle capability currently available for the production hierarchy required by the VSCS Production MVP:

```text
Project
→ Production
→ Episode / Film / Trailer
→ Sequence
→ Scene
→ Shot
→ Clip
```

The audit is intentionally evidence-driven. It assesses the current repository rather than the intended architecture and determines the smallest implementation sequence required to make the hierarchy complete, editable, testable, and suitable for the Xorix production workflow.

This phase does not redesign working Story, Scene, or Shot foundations. It identifies what can be retained, what is incomplete, and what must be introduced next.

## 2. Governing Requirements

The lifecycle target for every applicable production object is:

```text
Create
→ View
→ Edit
→ Duplicate
→ Reorder
→ Validate
→ Approve
→ Archive
→ Controlled Delete
→ Inspect History
→ Inspect Dependencies
```

Not every object requires every operation. For example, a Clip may not require approval independently in the first MVP release, while Production, Scene, and Shot require explicit readiness and approval states.

The audit is governed by:

- `VSCS_Production_MVP_Roadmap.md`;
- `VSCS_Video_Production_Workflow.md`;
- `Phase_17_6_1_2_Production_Object_Model.md`;
- `Phase_17_6_2_Functional_Gap_Analysis.md`;
- the Production Before Perfection principle;
- the 80/20 Production Rule;
- Progressive Disclosure;
- Xorix production validation.

## 3. Repository Evidence Reviewed

The audit reviewed the current implementation represented by:

```text
src/vscs/application/story/containers.py
src/vscs/application/story/service.py
src/vscs/application/shots/models.py
src/vscs/application/shots/service.py
src/vscs/presentation/dialogs/scene_editor_dialog.py
src/vscs/presentation/dialogs/shot_planner_dialog.py
src/vscs/presentation/widgets/story_browser.py
src/vscs/presentation/widgets/story_browser_v2.py
src/vscs/presentation/widgets/shot_planning_story_browser.py
tests/unit/test_shot_planning_service.py
```

Supporting bootstrap, project, ACPP, asset-resolution, Prompt Graph, and Story integration behavior was considered where it affects ownership and downstream dependencies.

## 4. Executive Finding

The repository contains a strong **Scene and Shot planning foundation**, but it does not yet contain a complete production-object hierarchy.

The current effective hierarchy is:

```text
Open Project
→ Free-form Production Container ID
→ Scene
→ Persistent Production Shot
→ ACPP / Prompt Graph downstream data
```

Production containers such as episodes, films, trailers, teasers, and promotional productions are currently inferred from string IDs. They are not persistent first-class objects with names, metadata, status, runtime targets, ownership, lifecycle operations, or approval history.

The main lifecycle gap is therefore not Scene or Shot creation. It is the missing ownership layer above Scene and the missing executable subdivision below Shot.

## 5. Lifecycle Status Vocabulary

The following audit classifications are used:

| Status | Meaning |
|---|---|
| Complete | Implemented in service and usable from the UI with suitable validation. |
| Partial | Some behavior exists, but lifecycle, UI, validation, or dependency safety is incomplete. |
| Backend Only | Service behavior exists but is not fully exposed through the production workflow. |
| Identifier Only | Represented only as a string, enum, or inferred naming convention. |
| Missing | No first-class model, service, persistence, or UI exists. |
| Deferred | Deliberately outside the Production MVP critical path. |

## 6. Production Object Lifecycle Matrix

| Object | Create | View | Edit | Duplicate | Reorder | Approve | Archive | Delete | History | Dependency Safety | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Project | Yes | Yes | Partial | No | N/A | No | No | Partial | No | Partial | Partial |
| Production | No | No | No | No | No | No | No | No | No | No | Missing |
| Episode / Film / Trailer | ID only | Inferred | ID field only | No | No | No | No | No | No | No | Identifier Only |
| Sequence | No | No | No | No | No | No | No | No | No | No | Missing |
| Scene | Yes | Yes | Yes | No | Manual sequence | No | No | Yes | No | No cascade guard | Partial |
| Shot | Yes | Yes | Yes | No | Yes | Status field | No | Yes | No | Partial | Mostly Complete |
| Clip | No | No | No | No | No | No | No | No | No | No | Missing |

## 7. Object-by-Object Findings

### 7.1 Project

The Project framework provides a tested storage and active-project boundary. It is sufficient as the ownership root for the next implementation phases.

Current strengths:

- project creation and opening;
- stable project directory;
- application-service integration;
- project-backed persistence for scenes, shots, assets, CAPs, references, and prompt data;
- test-mode isolation.

Current lifecycle gaps relevant to the Production MVP:

- project metadata editing is not yet a coherent production-facing workflow;
- no production list or active production context exists inside the project;
- archive, duplicate, and version migration are not exposed as a complete user workflow;
- project deletion and dependency behavior require a separate later review.

**Decision:** Retain the current Project architecture. Do not redesign it during Phase 18.1. The immediate P0 requirement is to add Production ownership beneath it.

### 7.2 Production

No first-class persistent Production object currently exists.

The target Production object must own one commercial output, such as:

- a series;
- a season-independent special;
- a film;
- a short film;
- a trailer;
- a teaser;
- a promotional video;
- a production test.

Required minimum MVP properties:

- stable production ID;
- project ownership;
- production type;
- title and description;
- target runtime;
- aspect ratio;
- frame rate;
- Preview and Production quality defaults;
- production status;
- story order and production order policy;
- active production context.

Required minimum lifecycle:

```text
Create
→ View
→ Edit
→ Duplicate
→ Validate
→ Archive
→ Controlled Delete
```

Approval can initially occur through readiness and Production Lock workflows rather than a complex approval service.

**Finding:** Production is the largest missing P0 ownership object.

### 7.3 Episode, Film, Trailer, and Other Production Containers

`ProductionContainerType` currently provides useful type vocabulary and default IDs for:

- episode;
- film;
- short;
- trailer;
- teaser;
- promo;
- test;
- special.

The current implementation also provides:

- type inference from IDs;
- ID normalization;
- scene-ID generation.

However, these are identifier utilities rather than lifecycle objects.

The current Scene model stores its owner in the legacy-compatible `episode_id` field. This field can contain a trailer, film, or other container ID, but it cannot provide:

- container title;
- synopsis;
- runtime target;
- parent Production ID;
- status;
- ordering;
- approval;
- archive state;
- readiness;
- metadata editing.

**Decision:** Retain `ProductionContainerType`, `infer_container_type()`, and ID-generation behavior for compatibility. Introduce a persistent Production Container model and service rather than replacing the existing ID scheme abruptly.

### 7.4 Sequence

No first-class Sequence object exists.

Scenes currently belong directly to a production-container ID and are ordered by `sequence_number`. This is sufficient for simple tests and early trailers, but it cannot represent:

- acts;
- trailer beats;
- multi-scene narrative sequences;
- sequence runtime;
- sequence purpose;
- sequence-level continuity;
- sequence-level readiness.

**MVP decision:** Sequence is P0 for episodes and long trailers, but it should be implemented after Production and Episode/Trailer containers. The first version may use a lightweight ordered container without advanced continuity or approval behavior.

### 7.5 Scene

Scene is a persistent first-class object with a working service and editor.

Current strengths:

- stable generated Scene ID;
- create and replace semantics through `save_scene()`;
- view in Story Browser;
- edit through `SceneEditorDialog`;
- delete through Story Browser;
- location selection by asset browser data;
- participant and required-asset selection;
- dialogue, time of day, transition, and estimated duration;
- deterministic storage order;
- generic container-ID compatibility;
- SSIE planning support.

Lifecycle gaps:

- no explicit duplicate operation;
- no service-level reorder operation;
- sequence is edited manually rather than managed as an ordered collection;
- no status field;
- no readiness result;
- no approval or lock state;
- no archive state;
- no version or revision history;
- delete does not guard or cascade dependent persistent Shots, ACPPs, Prompt Graphs, or compiled outputs;
- no dependency-impact preview before edit or delete;
- scene entry and exit continuity are not yet structured first-class state objects;
- no first-class Sequence parent;
- legacy `episode_id` naming exposes implementation history in the UI.

**Decision:** Retain `StoryService`, Scene persistence, Scene Editor, and asset selectors. Extend them incrementally after Production ownership is introduced.

### 7.6 Shot

Shot is the most complete production object in the audited hierarchy.

Current strengths:

- persistent `ProductionShot` model;
- stable generated Shot ID;
- create and replace through `save_shot()`;
- view in Story Browser v2;
- edit in Shot Planner;
- delete;
- deterministic per-scene ordering;
- explicit reorder service;
- camera, lighting, continuity, blocking, dialogue, assets, storyboard, and duration fields;
- Draft, Ready, and Approved status vocabulary;
- tested persistence, replacement, deletion, identity generation, and reordering;
- downstream ACPP and Prompt Graph integration.

Lifecycle gaps:

- no explicit duplicate operation;
- status transitions are not governed or validated;
- an Approved shot can be replaced without an unlock or revision workflow;
- no archive or supersede state;
- no version history;
- delete does not perform dependency-impact analysis;
- no dedicated controlled-delete policy for ACPP, Prompt Graph, compiled package, render, or continuity dependencies;
- no Clip subdivision;
- no formal readiness result combining assets, CAPs, references, physical reality, workflow, and output configuration;
- no scene-duration coverage validation;
- no approved-shot lock suitable for Production Lock.

**Decision:** Retain the existing Shot domain and service. Add lifecycle governance rather than replacing it.

### 7.7 Clip

No first-class Clip object exists.

A Clip is required when a cinematic Shot must be divided because of:

- renderer duration limits;
- start/end-frame continuity;
- dialogue segmentation;
- partial rerendering;
- multi-stage effects;
- lip-sync boundaries;
- workflow-specific frame limits.

Required minimum MVP properties:

- stable Clip ID;
- parent Shot ID;
- sequence number;
- target duration or frame range;
- purpose;
- transition-in and transition-out notes;
- renderer status;
- output lineage.

Required minimum lifecycle:

```text
Create automatically or manually
→ View
→ Edit boundaries
→ Reorder
→ Validate
→ Delete before production
```

Advanced independent approval and archive behavior can be deferred until after the first commercial trailer.

**Finding:** Clip is missing and becomes production-critical before real rendering integration.

## 8. Cross-Object Integrity Findings

### 8.1 Ownership is currently implicit

Scenes use a free-form production-container ID. Shots use a Scene ID. This supports persistence but does not prove that the full parent hierarchy exists.

Required ownership validation:

```text
Scene must reference an existing Production Container
Shot must reference an existing Scene
Clip must reference an existing Shot
```

### 8.2 Deletion is not dependency safe

Current Scene and Shot deletion removes the selected object from its JSON store, but the lifecycle does not yet provide a unified dependency impact report.

A controlled deletion must identify at least:

- child Scenes, Shots, and Clips;
- ACPP packages;
- Prompt Graphs;
- compilation history;
- dependency index records;
- render outputs;
- timeline usage;
- approval and review records.

For the Production MVP, referenced objects should generally be archived or require explicit cascade confirmation rather than being silently deleted.

### 8.3 Status vocabularies are inconsistent

Shot has Draft, Ready, and Approved. Scene and container objects do not yet expose equivalent production status.

A shared minimum status model is required:

```text
Draft
→ Ready for Review
→ Approved
→ In Production
→ Completed
→ Archived
```

Exception states:

```text
Blocked
Revision Required
Rejected
Cancelled
Superseded
```

The first MVP implementation should use only the subset required by each object.

### 8.4 Editing approved objects is uncontrolled

Current replace semantics are appropriate for drafts but insufficient once objects are approved or used by generated media.

Required rule:

- Draft objects may be edited directly.
- Approved objects require unlock, revision creation, or explicit approval invalidation.
- Changes must trigger dependency propagation at the lowest valid invalidation level.

### 8.5 History is absent

Scene and Shot persistence stores only the latest object state.

The Production MVP does not require a complex event-sourced architecture, but it does require enough provenance to answer:

- what changed;
- when it changed;
- which approved version produced a render;
- which downstream objects became stale.

A lightweight revision and audit-record mechanism is sufficient for v1.

## 9. Reuse Decisions

The following current components should be retained:

- `ProjectService` as the project ownership and storage boundary;
- `ProductionContainerType` and existing ID normalization utilities;
- `StoryService` Scene persistence;
- `SceneEditorDialog` and its asset-selection patterns;
- `ShotPlanningService` and `ProductionShot`;
- `ShotPlannerDialog`;
- Story Browser v2 hierarchy and production-shot integration;
- existing ACPP, Prompt Graph, asset-resolution, dependency-propagation, and compilation services.

No rewrite of the Story or Shot subsystems is justified.

## 10. Required Implementation Sequence

The audit recommends the following sequence.

### Phase 18.1.2 — Production and Container Lifecycle Foundation

Implement:

- persistent Production object;
- persistent Production Container object;
- project ownership;
- production type, title, runtime, status, and defaults;
- create, view, edit, duplicate, archive, and controlled delete;
- compatibility with existing Scene container IDs;
- migration or discovery of legacy container IDs already present in `scenes.json`;
- focused service, persistence, bootstrap, and migration tests.

### Phase 18.1.3 — Production Navigator Foundation

Implement:

- Project → Production → Container → Scene → Shot hierarchy;
- current context;
- selection preservation;
- production-facing labels rather than raw IDs;
- Next Action placeholder contract;
- Progressive Disclosure.

### Phase 18.1.4 — Scene Lifecycle Completion

Implement:

- duplicate Scene;
- reorder Scenes within a container;
- Scene status and readiness baseline;
- archive or controlled delete;
- dependency-impact reporting;
- legacy `episode_id` compatibility behind a production-container abstraction.

### Phase 18.1.5 — Shot Lifecycle Completion

Implement:

- duplicate Shot;
- governed status transitions;
- approved-shot lock or revision behavior;
- archive and supersede behavior where required;
- controlled deletion with dependency impact;
- duration coverage reporting.

### Phase 18.1.6 — Clip Foundation and Integration Tests

Implement:

- Clip model and persistence;
- automatic one-Clip default for a Shot;
- manual subdivision;
- ordering and duration validation;
- renderer-facing identity;
- end-to-end hierarchy tests;
- Xorix trailer lifecycle validation.

## 11. Production MVP Priority Decisions

### P0 — Must be implemented now

- Production object;
- Episode/Film/Trailer container object;
- parent ownership validation;
- production navigation;
- Scene duplicate and reorder;
- Shot duplicate and governed status;
- Clip foundation;
- dependency-aware delete or archive;
- contextual Help for new lifecycle UI.

### P1 — Implement when it materially improves production

- advanced version comparison;
- bulk duplication;
- visual dependency graph;
- production templates beyond the initial trailer/episode templates;
- detailed audit-history browser;
- sophisticated archive restoration.

### P2 — Platform Evolution

- multi-user ownership and permissions;
- concurrent editing;
- cloud project synchronization;
- branch-and-merge production revisions;
- enterprise approval chains.

## 12. Automated Validation Baseline

Phase 18.1.1 introduces no runtime behavior change. Existing characterization tests provide the baseline for the retained Scene and Shot services.

Run:

```powershell
ruff check `
    src/vscs/application/story `
    src/vscs/application/shots `
    src/vscs/presentation/dialogs/scene_editor_dialog.py `
    src/vscs/presentation/dialogs/shot_planner_dialog.py `
    src/vscs/presentation/widgets/story_browser.py `
    src/vscs/presentation/widgets/story_browser_v2.py `
    src/vscs/presentation/widgets/shot_planning_story_browser.py `
    tests/unit/test_shot_planning_service.py
```

Run the existing lifecycle characterization suite:

```powershell
pytest `
    tests/unit/test_story_service.py `
    tests/unit/test_scene_editor_dialog.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_story_browser_v2.py `
    tests/unit/test_shot_planning_service.py `
    tests/unit/test_shot_planner_dialog.py `
    tests/unit/test_shot_planning_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

If one of the named legacy test files does not exist in the local checkout, omit only that path and record the omission during approval. The implementation phase that owns the affected object must add replacement coverage.

## 13. Manual UI Audit Plan

No new UI behavior is introduced, but the following baseline audit should be performed once to confirm the repository assessment.

### Preconditions

- Open a test project.
- Ensure at least one Location asset and one Character asset exist.

### Test 1 — Scene lifecycle baseline

1. Open the Story workspace.
2. Create a Scene.
3. Save it.
4. Edit its name and summary.
5. Save and reopen it.
6. Delete the Scene after the test.

**Pass criteria:** Create, view, edit, persist, and delete work. No Duplicate, Archive, Approve, History, or dedicated Reorder action is present.

### Test 2 — Shot lifecycle baseline

1. Create or select a Scene.
2. Open Shot Planner.
3. Create two Shots.
4. Edit one Shot.
5. Reorder the Shots.
6. Delete one Shot.

**Pass criteria:** Create, view, edit, persist, reorder, and delete work. No Duplicate, Archive, Revision History, or governed approval lock is present.

### Test 3 — Production ownership baseline

1. Inspect the Story hierarchy above the Scene.
2. Attempt to edit the Episode, Trailer, or Production metadata independently of the Scene.

**Pass criteria:** The audit is confirmed when no first-class Production or Production Container editor is available and ownership is represented primarily by container ID.

### Test 4 — Clip baseline

1. Inspect a persistent Production Shot.
2. Look for a Clip subdivision, Clip editor, or Clip hierarchy.

**Pass criteria:** The audit is confirmed when no first-class Clip capability is available.

## 14. Acceptance Criteria

Phase 18.1.1 is approved when:

- the lifecycle matrix accurately reflects the repository;
- retained components and missing capabilities are clearly distinguished;
- no working Scene or Shot subsystem is scheduled for unnecessary replacement;
- Production and Clip are identified as missing first-class objects;
- Scene and Shot lifecycle gaps are explicitly recorded;
- the implementation order is actionable and Production MVP focused;
- the automated baseline remains green;
- the manual UI audit confirms the documented current state.

## 15. Xorix Production Impact

This audit does not directly add a new production control. It removes uncertainty about the next implementation work.

For the Xorix trailer, it establishes that VSCS already supports:

- persistent Scenes;
- persistent Shots;
- Shot ordering;
- asset assignment;
- ACPP and prompt preparation downstream.

It also establishes the blockers that must be closed before a complete trailer can be managed as one production:

- no persistent Trailer production object;
- no editable trailer metadata or runtime target;
- no explicit trailer sequence/beat ownership;
- no complete Scene lifecycle;
- no governed Shot approval lifecycle;
- no Clip subdivision for renderer execution.

The next capability unlocked by Phase 18.1.2 will be the ability to create and edit a persistent **Xorix Trailer production and its owned production container**, rather than managing trailer Scenes through free-form IDs.

## 16. Repository Impact

### Files created

```text
docs/engineering/Phase_18_1_1_Production_Object_Lifecycle_Audit.md
```

### Runtime source files modified

None.

### Tests modified

None. Existing tests are used as the characterization baseline.

### Recommended commit message

```text
Add Phase 18.1.1 production object lifecycle audit
```

## 17. Phase Decision

**Phase 18.1.1 result:** Audit complete.

**Architecture decision:** Extend the current Story and Shot foundations. Do not rewrite them.

**Next approved implementation candidate:**

```text
Phase 18.1.2 — Production and Container Lifecycle Foundation
```
