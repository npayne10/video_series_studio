# Phase 18.1.7 — Story Workspace Help

## Status

Implemented.

## Objective

Provide comprehensive, context-sensitive help inside the Story Workspace without changing Story lifecycle, Scene, Shot, asset, or ACPP behaviour.

## Implemented capabilities

The Story Workspace Help dialog contains these sections:

1. Overview
2. Story Lifecycle
3. Story Metadata
4. Story Governance
5. Source Files
6. Production Workflow
7. Best Practices
8. Physical Reality
9. Related Workspaces

The Help button is available whether or not a Story has been created or selected.

## Production workflow coverage

The help content describes the approved Story-driven workflow:

```text
Idea
→ Story
→ Story Analysis
→ Story Approval
→ Production Planning
→ Assets and CAPs
→ Scenes and Shots
→ Prompt Generation
→ Rendering
→ Lip-sync and Post Production
→ Release
```

## Physical Reality coverage

The help reminds users that gravity, inertia, momentum, materials, lighting, biology, and engineering remain internally consistent unless Story Canon explicitly defines an exception.

## Files created

- `src/vscs/presentation/help/story_workspace_help.py`
- `tests/unit/test_story_workspace_help.py`
- `docs/engineering/Phase_18_1_7_Story_Workspace_Help.md`

## Files modified

- `src/vscs/presentation/help/__init__.py`
- `src/vscs/presentation/widgets/browseable_story_workspace.py`

## Automated validation

```powershell
ruff check `
    src/vscs/presentation/help/story_workspace_help.py `
    src/vscs/presentation/help/__init__.py `
    src/vscs/presentation/widgets/browseable_story_workspace.py `
    tests/unit/test_story_workspace_help.py
```

```powershell
pytest `
    tests/unit/test_story_workspace_help.py `
    tests/unit/test_browseable_story_workspace.py `
    tests/unit/test_story_workspace.py `
    tests/integration/test_story_workspace_pipeline.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_shot_planning_story_browser.py `
    tests/unit/test_acpp_story_browser.py -v
```

## Manual UI test plan

1. Start VSCS and open or create a project.
2. Open the Story section.
3. Click **Help** with no Story selected.
4. Confirm the Story Workspace Help dialog opens.
5. Select each help section.
6. Confirm the displayed content changes to match the selected section.
7. Close the Help dialog.
8. Create or select a Story and open Help again.
9. Confirm Story, Scene, Shot Planner, asset, and ACPP controls remain usable after closing Help.

## Pass criteria

- Help opens regardless of Story state.
- All nine approved sections are present.
- Workflow and Physical Reality content is readable.
- The dialog can be closed without changing production data.
- Existing Story Browser, Scene, Shot Planner, asset, and ACPP behaviour remains unchanged.
