# Phase 18.1.6 — Story Workspace UI

## Status

Implemented for validation.

## Objective

Expose the first-class Story lifecycle, metadata, status, and approval capabilities through one production-facing workspace while preserving the existing Scene, Shot, asset-assignment, and ACPP workflows.

## Implemented UI

The Story section now opens a Story-first workspace containing:

- Story list with lifecycle status.
- Create Story.
- Edit Story and metadata.
- Duplicate Story.
- Mark Story as Analysed.
- Approve Story Canon.
- Lock and unlock Story Canon.
- Reopen approved Canon for revision.
- Archive and restore Story.
- Show or hide archived Stories.
- Metadata-completeness percentage.
- Missing required metadata fields.
- Approval-readiness indication.
- Contextual Help.
- The existing production hierarchy browser below the Story controls.

## Story Editor

The guided Story editor supports:

- Title.
- Description.
- Source type and source path.
- Synopsis.
- Genres.
- Themes.
- Target audience.
- Language.
- Author.
- Estimated runtime.
- Keywords.
- Notes.

## Workflow

```text
Create or Import Story
→ Complete Metadata
→ Mark Analysed
→ Approve Story Canon
→ Lock Canon
→ Continue Production Planning
```

Editing an Analysed or Approved Story invalidates the later state as defined by the backend lifecycle. Locked Stories cannot be edited until unlocked or reopened through approval governance.

## Repository Impact

### Created

- `src/vscs/presentation/widgets/story_workspace.py`
- `tests/unit/test_story_workspace.py`
- `tests/integration/test_story_workspace_pipeline.py`
- `docs/engineering/Phase_18_1_6_Story_Workspace_UI.md`

### Modified

- `src/vscs/presentation/story_integration.py`

## Automated Validation

```powershell
ruff check `
    src/vscs/application/story `
    src/vscs/presentation/story_integration.py `
    src/vscs/presentation/widgets/story_workspace.py `
    tests/unit/test_story_workspace.py `
    tests/integration/test_story_workspace_pipeline.py
```

```powershell
pytest `
    tests/unit/test_story_workspace.py `
    tests/integration/test_story_workspace_pipeline.py `
    tests/unit/test_story_approval.py `
    tests/unit/test_story_status.py `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_shot_planning_story_browser.py `
    tests/unit/test_acpp_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

## Manual UI Test Plan

### Test 1 — Empty Story Workspace

1. Start VSCS.
2. Create or open a project with no first-class Story.
3. Open the Story section.

Pass criteria:

- The Story Workspace is visible.
- It explains that no Story is defined.
- `New Story` is enabled.
- The existing production browser remains visible below the Story area.

### Test 2 — Create Story

1. Select `New Story`.
2. Enter a title, synopsis, genre, theme, target audience, language, and author.
3. Save.

Pass criteria:

- The Story appears in the list with a stable ID and Draft or Imported status.
- Metadata completeness is shown.
- The details panel displays the supplied Story information.
- Data remains after closing and reopening the project.

### Test 3 — Edit and Duplicate

1. Select the Story and choose `Edit`.
2. Change metadata and save.
3. Select `Duplicate`.

Pass criteria:

- Edits persist.
- The duplicate receives a new Story ID.
- The duplicate is editable and starts as Draft.
- Metadata is copied independently.

### Test 4 — Analysis and Approval

1. Complete all required metadata.
2. Select `Mark Analysed`.
3. Select `Approve`.
4. Select `Lock`.

Pass criteria:

- Status progresses from Draft or Imported to Analysed, Approved, and Locked.
- Approve remains unavailable until metadata is complete and status is Analysed.
- Edit is disabled when the Story is Locked.
- Unlock and Reopen become available at the correct stages.

### Test 5 — Unlock and Revision

1. Unlock the Locked Story.
2. Reopen it for revision.
3. Edit the Story.

Pass criteria:

- Unlock returns the Story to Approved.
- Reopen returns the Story to Analysed.
- Editing returns the Story to an editable state.
- Approval must be performed again after revision.

### Test 6 — Archive and Restore

1. Archive a Story.
2. Enable `Show archived`.
3. Select the archived Story and restore it.

Pass criteria:

- Archived Stories disappear from the default active list.
- They appear when `Show archived` is enabled.
- Restore returns the Story to its previous workflow state.

### Test 7 — Existing Production Workflow Regression

1. Use the embedded production browser.
2. Create or edit a Scene.
3. Open the Shot Planner.
4. Open the ACPP Editor for a Shot.

Pass criteria:

- Existing Scene, Shot, asset, and ACPP functions remain operational.
- Story Workspace refresh does not remove or corrupt existing production data.

## Expected Outcome

The Story is now the first user-facing creative object beneath the Project. A creator can define and govern Story Canon before entering production planning, while all previously implemented production tools remain available in the same Story section.
