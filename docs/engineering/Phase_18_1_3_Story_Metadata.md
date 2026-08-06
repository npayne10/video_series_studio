# Phase 18.1.3 — Story Metadata

**Document ID:** VSCS-ENG-18.1.3  
**Version:** 1.0  
**Status:** Implemented — Awaiting Validation  
**Parent Phase:** 18.1 — Story Workspace Foundation  
**Priority:** P0 — Production Critical  

## 1. Objective

Provide structured creative and editorial metadata for every first-class Story created by the Phase 18.1.2 lifecycle foundation.

This phase does not add Story analysis, approval, locking, version comparison, or the final Story Workspace editor. It supplies the persistent metadata contract and readiness information those later phases require.

## 2. Implemented Metadata

Each Story may define:

- Synopsis
- Genres
- Themes
- Target audience
- Language
- Author
- Estimated runtime in minutes
- Keywords
- Production and editorial notes
- Last-updated timestamp

Metadata is keyed by the stable Story identity, for example `STORY-001`.

## 3. Persistence

Metadata is stored atomically in:

```text
<project>/story/story_metadata.json
```

The independent metadata registry preserves compatibility with projects created before Phase 18.1.3 and allows later analysis and approval state to evolve without overloading the basic Story lifecycle record.

## 4. Lifecycle Rules

- Metadata can only be saved for an existing Story.
- Archived Stories must be restored before metadata can be edited.
- Estimated runtime must be greater than zero when supplied.
- Genre, theme, and keyword values are trimmed, deduplicated, and deterministically sorted.
- Metadata can be removed without deleting the owning Story.

## 5. Completeness

The service exposes a deterministic completeness result for future Story Workspace readiness displays.

Required metadata fields are:

- Synopsis
- Genres
- Themes
- Target audience
- Language
- Author

The result includes:

- Completed fields
- Missing fields
- Percentage complete
- Complete/incomplete state

## 6. Repository Impact

### Created

```text
src/vscs/application/story/metadata.py
tests/unit/test_story_metadata.py
tests/unit/test_story_metadata_bootstrap.py
docs/engineering/Phase_18_1_3_Story_Metadata.md
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
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_metadata_bootstrap.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py
```

### Pytest

```powershell
pytest `
    tests/unit/test_story_metadata.py `
    tests/unit/test_story_metadata_bootstrap.py `
    tests/unit/test_story_lifecycle.py `
    tests/unit/test_story_lifecycle_bootstrap.py `
    tests/unit/test_story_service.py `
    tests/unit/test_story_browser.py `
    tests/unit/test_application_bootstrap.py -v
```

## 8. Manual UI Regression Test

This phase adds no metadata editor UI.

1. Start VSCS.
2. Create or open a project.
3. Open the Story section.
4. Confirm the existing Story Browser loads without errors.
5. Create or edit a Scene.
6. Close and reopen the project.
7. Confirm the Scene remains available.

### Pass Criteria

- VSCS starts without an exception.
- The Story section opens normally.
- Existing Scene and Shot functionality is unchanged.
- No visible regression occurs in project open, close, or refresh behaviour.

## 9. Acceptance Criteria

- Story metadata persists by stable Story ID.
- Existing projects without metadata files remain valid.
- Metadata values are normalized deterministically.
- Archived Stories cannot be edited.
- Runtime validation is enforced.
- Completeness identifies every missing required field.
- Bootstrap registration reuses the shared Story lifecycle service.
- Ruff and pytest pass.

## 10. Xorix Production Value

This phase provides the structured information needed to register Xorix as a first-class Story with its synopsis, science-fiction genre, themes, target audience, language, S.S. Drake authorship, expected runtime, keywords, and production notes. The later Story Workspace UI can now expose these fields without inventing a second storage model.
