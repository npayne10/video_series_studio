# Phase 18.1.8 — Story Workspace Tests

## Status

Implemented.

## Purpose

Complete Phase 18.1 with consolidated automated and manual verification of the Story Workspace foundation introduced through Phases 18.1.2–18.1.7.

## Automated Coverage

The test suite verifies:

- First-class Story creation and stable identity.
- Story source type and source path persistence.
- Complete Story metadata and readiness.
- Draft or Imported to Analysed transition.
- Story approval and Canon locking.
- Persistent status and approval histories.
- Reloading Story state from project files.
- Locked Story protection.
- Governed reopening for revision.
- Metadata changes invalidating analysed state.
- Archive and restore preserving prior workflow state.
- Browse-enabled Story Workspace installation.
- Story Help availability and section completeness.
- Preservation of the inherited Story Browser, Shot Planner, and ACPP APIs.

## Files Created

- `tests/integration/test_story_workspace_foundation.py`
- `docs/engineering/Phase_18_1_8_Story_Workspace_Tests.md`

## Ruff

```powershell
ruff check `
    src/vscs/application/story `
    src/vscs/presentation/help/story_workspace_help.py `
    src/vscs/presentation/widgets/story_workspace.py `
    src/vscs/presentation/widgets/browseable_story_workspace.py `
    src/vscs/presentation/story_integration.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_approval.py `
    tests/unit/test_story_workspace.py `
    tests/unit/test_browseable_story_workspace.py `
    tests/unit/test_story_workspace_help.py `
    tests/integration/test_story_workspace_pipeline.py `
    tests/integration/test_story_workspace_foundation.py
```

## Pytest

```powershell
pytest `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_metadata_bootstrap.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_status_bootstrap.py `
    tests/unit/test_story_approval.py `
    tests/unit/test_story_approval_bootstrap.py `
    tests/unit/test_story_workspace.py `
    tests/unit/test_browseable_story_workspace.py `
    tests/unit/test_story_workspace_help.py `
    tests/integration/test_story_workspace_pipeline.py `
    tests/integration/test_story_workspace_foundation.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_shot_planning_story_browser.py `
    tests/unit/test_acpp_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

## Manual UI Test Plan

1. Start VSCS and create or open a project.
2. Open the Story workspace.
3. Create a Story and browse to a supported source file.
4. Complete all required metadata fields and save.
5. Confirm the Story appears with the expected source and readiness information.
6. Mark the Story as Analysed.
7. Approve and lock the Story.
8. Confirm Edit is disabled while locked.
9. Open Help and inspect all nine sections.
10. Unlock or reopen the Story and confirm editing becomes available as governed.
11. Archive the Story, enable Show archived, and restore it.
12. Confirm Scene, Shot Planner, asset, and ACPP functions remain available.
13. Close and reopen the project and confirm Story data persists.

## Manual Pass Criteria

- Source browsing populates the path and detects the source type.
- Metadata completeness reaches 100 percent when all required fields are present.
- Status controls enable only valid actions.
- Approved Canon can be locked.
- Locked Stories cannot be edited directly.
- Help opens independently of Story state and contains all approved sections.
- Archive and restore preserve the prior Story status.
- Existing Scene, Shot, asset, and ACPP functionality remains operational.
- Story identity, metadata, state, and histories persist after reopening the project.

## Acceptance Criteria

Phase 18.1 is complete when Ruff passes, the complete automated suite passes, and the manual UI test meets every pass criterion.

## Git Commit Message

`Complete Phase 18.1.8 Story Workspace tests`
