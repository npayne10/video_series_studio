# Phase 18.1.5 — Story Approval

**Document ID:** VSCS-ENG-18.1.5  
**Version:** 1.0  
**Status:** Implemented — Awaiting Validation  
**Priority:** P0 — Production Critical  
**Parent Phase:** 18.1 — Story Workspace Foundation  

## 1. Objective

Provide governed approval and locking for first-class Story Canon without allowing ordinary status operations to bypass approval authority.

## 2. Delivered Capability

The phase introduces `StoryApprovalService` with these governed operations:

- Approve an Analysed Story.
- Lock approved Story Canon.
- Unlock locked Canon while retaining Approved status.
- Reopen Approved or Locked Canon for controlled revision.
- Inspect current approval readiness and available actions.
- Retrieve latest approval decision.
- Retrieve immutable approval history.

## 3. Approval Preconditions

A Story can be approved only when:

- It exists and is active.
- Its current status is `Analysed`.
- Core Story metadata is complete.
- An approver identity is supplied.
- Approval notes are supplied.

Required metadata remains:

- Synopsis
- Genre
- Theme
- Target audience
- Language
- Author

## 4. Governed Lifecycle

```text
Analysed
    ↓ Approve
Approved
    ↓ Lock
Locked
    ↓ Unlock
Approved
```

A Story in either `Approved` or `Locked` state may be reopened:

```text
Approved / Locked
    ↓ Reopen for Revision
Analysed
```

Ordinary `StoryStatusService.transition()` operations continue to reject direct transitions into `Approved` or `Locked`.

## 5. Approval Records

Every decision records:

- Story ID
- Action
- Previous status
- New status
- Decision maker
- Decision notes
- UTC timestamp

Records are stored atomically in:

```text
<project>/story/story_approval_history.json
```

## 6. Repository Impact

### Created

```text
src/vscs/application/story/approval.py
tests/unit/test_story_approval.py
tests/unit/test_story_approval_bootstrap.py
docs/engineering/Phase_18_1_5_Story_Approval.md
```

### Modified

```text
src/vscs/application/story/bootstrap.py
src/vscs/application/story/__init__.py
src/vscs/presentation/story_integration.py
```

## 7. Automated Validation

### Ruff

```powershell
ruff check `
    src/vscs/application/story `
    src/vscs/presentation/story_integration.py `
    tests/unit/test_story_approval.py `
    tests/unit/test_story_approval_bootstrap.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_lifecycle.py
```

### Pytest

```powershell
pytest `
    tests/unit/test_story_approval.py `
    tests/unit/test_story_approval_bootstrap.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_status_bootstrap.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_metadata_bootstrap.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py `
    tests/unit/test_story_service.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

## 8. Manual UI Regression Test

This phase adds backend approval governance only. The approval UI is delivered by the later Story Workspace UI phase.

1. Start VSCS.
2. Create or open a project.
3. Open the Story section.
4. Create or edit an existing Scene.
5. Open the Shot Planner for that Scene.
6. Close and reopen the project.

### Pass Criteria

- VSCS starts without an exception.
- The Story section opens normally.
- Existing Scene and Shot workflows remain operational.
- No approval controls are expected yet.

## 9. Acceptance Criteria

The phase passes when:

- Approval is rejected for Draft or Imported Stories.
- Approval is rejected when required metadata is incomplete.
- Analysed Stories with complete metadata can be approved.
- Approved Stories can be locked.
- Locked Stories can be unlocked to Approved.
- Approved or Locked Stories can be reopened to Analysed.
- Invalid decision details do not mutate Story status.
- Approval history persists and remains queryable.
- Bootstrap reuses shared Story dependencies.
- Ruff and all specified tests pass.

## 10. Xorix Production Value

The Xorix source Story can now be formally approved as Story Canon and locked before productions are derived from it. This establishes a controlled creative baseline for the trailer, Episode 1, and later productions.
