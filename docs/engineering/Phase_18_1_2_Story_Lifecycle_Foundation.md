# Phase 18.1.2 — Story Lifecycle Foundation

**Document ID:** VSCS-ENG-18.1.2  
**Version:** 1.0  
**Status:** Implemented — Awaiting Local Verification  
**Parent Phase:** 18.1 — Story Workspace Foundation  
**Priority:** P0 — Production Critical  
**Reference Production:** Xorix

## 1. Objective

Introduce the first-class persistent `Story` object required by the Story-Driven Production workflow.

This phase establishes the lifecycle foundation beneath the Project and above all future Productions. It does not implement Story Analysis, approval, locking, version comparison, or the final Story Workspace UI.

## 2. Implemented Capability

The new lifecycle supports:

- create;
- inspect;
- list active stories;
- list archived stories;
- edit;
- duplicate;
- archive;
- restore;
- controlled permanent deletion;
- stable project-local Story IDs;
- source-type classification;
- draft and imported state detection;
- creation, update, and archive timestamps;
- atomic project-backed JSON persistence;
- dependency registration helper.

## 3. Story Identity

Stories receive deterministic project-local identities:

```text
STORY-001
STORY-002
STORY-003
```

Identity is never changed when the title, description, source, or lifecycle state changes.

## 4. Lifecycle Boundary

The states implemented in this foundation are:

```text
Draft
Imported
Archived
```

Later phases will extend the lifecycle with analysis, review, approval, locking, and revision states.

## 5. Safety Rules

- A Story title is mandatory.
- Archived Stories cannot be edited until restored.
- Permanent deletion is allowed only after archival.
- Duplicate Stories receive new identities and return to Draft state.
- Active listings exclude archived Stories unless explicitly requested.
- Writes use a temporary file and atomic replacement.

## 6. Persistence

The active project stores the lifecycle registry at:

```text
<project>/story/stories.json
```

This is separate from the existing structured Scene store:

```text
<project>/story/scenes.json
```

The separation preserves the existing Scene and Shot planning foundations while introducing the Story as their future parent creative object.

## 7. Repository Impact

### Files created

```text
src/vscs/application/story/lifecycle.py
src/vscs/application/story/bootstrap.py
tests/unit/test_story_lifecycle.py
tests/unit/test_story_lifecycle_bootstrap.py
docs/engineering/Phase_18_1_2_Story_Lifecycle_Foundation.md
```

### Files modified

```text
src/vscs/application/story/__init__.py
```

## 8. Deferred Capability

The following remains outside Phase 18.1.2:

- Story import file handling;
- Story text editing;
- Story metadata expansion;
- Story analysis;
- Story approval;
- Story locking;
- Story version history and comparison;
- Story-to-Production creation;
- Story Workspace UI;
- linking existing Scenes to a selected Story.

## 9. Automated Verification

Run Ruff:

```powershell
ruff check `
    src/vscs/application/story `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py
```

Run focused tests:

```powershell
pytest `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py `
    tests/unit/test_story_service.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

### Automated PASS criteria

- Ruff reports no errors.
- All lifecycle tests pass.
- Existing Scene and Story Browser tests remain green.
- Existing application bootstrap tests remain green.

## 10. Manual UI Regression Test

This phase introduces no new Story lifecycle UI.

1. Start VSCS.
2. Create or open a project.
3. Open the existing Story Browser.
4. Create a Scene.
5. Edit the Scene.
6. Generate its SSIE plan if available.
7. Close and reopen the project.
8. Confirm the Scene remains present and editable.

### Manual PASS criteria

- Existing Story Browser behaviour is unchanged.
- Existing Scene creation, editing, persistence, and planning continue to work.
- No new startup or project-open errors appear.

## 11. Xorix Production Value

This phase creates the persistent creative root required to register the Xorix manuscript as a first-class Story before deriving the Xorix trailer and streaming episodes as separate Productions.

## 12. Expected Outcome

VSCS now has a stable backend lifecycle for multiple Stories inside one Project. The next phase can build the Story Workspace and metadata UI on this foundation without overloading the existing Scene service or treating Scenes as the root of the creative hierarchy.

## 13. Recommended Commit Message

```text
Implement Phase 18.1.2 Story Lifecycle Foundation
```
