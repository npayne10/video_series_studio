# Phase 18.1.4 — Story Status

**Document ID:** VSCS-ENG-18.1.4  
**Version:** 1.0  
**Status:** Implemented — Awaiting Validation  
**Parent Phase:** 18.1 — Story Workspace Foundation  
**Priority:** P0 — Production Critical  

## 1. Objective

Provide an explicit, validated and traceable Story status workflow beneath the active VSCS Project.

This phase establishes status vocabulary, transition rules, transition history and status restoration. Approval identity, approval records and locking authority remain reserved for Phase 18.1.5.

## 2. Status Model

The Story lifecycle now supports:

```text
Draft
Imported
Analysed
Approved
Locked
Archived
```

The complete vocabulary is defined now so later workflow phases share one stable model.

Ordinary status operations available in this phase are:

- Draft or Imported to Analysed.
- Imported to Draft.
- Analysed back to Draft or Imported.
- Any active state to Archived.
- Archived back to its exact pre-archive state.

Direct transitions to `Approved` and `Locked` are rejected. Those states must be entered through the dedicated Story approval workflow.

## 3. Functional Deliverables

Implemented:

- `StoryStatusService`.
- `StoryStatusSnapshot`.
- `StoryStatusTransition`.
- Validated transition graph.
- Persistent chronological transition history.
- Required reason and actor for every transition.
- Archive and restore history.
- Preservation of pre-archive status.
- Locked Story edit protection.
- Automatic invalidation of Analysed or Approved status when Story source details are edited.
- Backward-compatible loading of existing `stories.json` records.

## 4. Persistence

Current Story status remains stored in:

```text
<project>/story/stories.json
```

Transition history is stored in:

```text
<project>/story/story_status_history.json
```

Both files use atomic temporary-file replacement.

## 5. Repository Impact

### Created

```text
src/vscs/application/story/status.py
tests/unit/test_story_status.py
tests/unit/test_story_status_bootstrap.py
docs/engineering/Phase_18_1_4_Story_Status.md
```

### Modified

```text
src/vscs/application/story/lifecycle.py
src/vscs/application/story/bootstrap.py
src/vscs/application/story/__init__.py
src/vscs/presentation/story_integration.py
```

## 6. Automated Validation

### Ruff

```powershell
ruff check `
    src/vscs/application/story `
    src/vscs/presentation/story_integration.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_status_bootstrap.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_metadata.py
```

### Pytest

```powershell
pytest `
    tests/unit/test_story_status.py `
    tests/unit/test_story_status_bootstrap.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_metadata_bootstrap.py `
    tests/unit/test_story_service.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

## 7. Manual UI Regression Plan

No Story status controls are exposed in the UI during this phase.

1. Start VSCS.
2. Create or open a project.
3. Open the Story section.
4. Create or edit a Scene.
5. Open the Shot Planner and inspect an existing Shot.
6. Close and reopen the project.

### Pass Criteria

- VSCS starts without errors.
- The Story section opens normally.
- Existing Scene and Shot functionality remains unchanged.
- No new status UI is expected yet.

## 8. Acceptance Criteria

- The complete Story status vocabulary exists.
- Ordinary transitions are validated.
- Approval and lock transitions cannot bypass the future approval workflow.
- Every transition records reason, actor and timestamp.
- Archive and restore preserve the prior status.
- Invalid transition input cannot mutate Story state.
- Locked Stories cannot be edited through the ordinary lifecycle service.
- Existing Story lifecycle, metadata, Scene and Shot tests remain passing.

## 9. Production Value

VSCS can now determine where each Story is in the creative workflow and retain a traceable history of changes. This provides the state foundation required by Story approval, the future Story Workspace dashboard and recommended next actions.

## 10. Next Phase

```text
Phase 18.1.5 — Story Approval
```
