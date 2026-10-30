# B.5.19a — Governed Production Plan Authority Adapter

Status: Initial adapter committed, **not accepted** pending Windows lint, mypy, regression and operator project-path verification.

## Repository finding
The existing Story Workspace inherits `StoryBrowserV2Widget`. Its `refresh()` reads `StoryService.list_scenes()` (persisted `<project>/story/scenes.json`). The Shot Planner operates through `ShotPlanningService` (`<project>/story/shots.json`). Story Browser may additionally project in-memory scene plans; those plans alone are **not** authoritative persisted Shot text.

Therefore the earlier claim that Story Workspace definitely uses a second separate canonical persisted Scene/Shot repository was **not established**. If Story Workspace shows a Scene but `Assign Story Scenes` reports none, investigate active project directory and actual source data, rather than creating duplicates or inventing a new authority.

## Implemented
- `GovernedProductionPlanAdapter` wraps the two existing project-backed planning services read-only. It reports source paths, counts, Scene IDs and orphan Shot IDs.
- `Assign Story Scenes (Reviewed)` now explicitly identifies the active Scene/Shot source paths when no scenes are found, without modifying any project data.
- CAP review retrieves Shot evidence via adapter, keeping existing operator-confirmed ownership and freshness checks. Orphan Shots are rejected rather than silently accepted.
- Synthetic tests cover source paths, no side effects and orphan rejection.
- No second Scene or Shot store, no backfill/migration, no paid provider calls, no CAP/Canon writes, no H3 execution. Original audit is not modified.

## Outstanding
- We must compare the diagnostic paths to the actual project in the screenshot and determine whether the intended project is open and whether `story/scenes.json` contains the expected Scene.
- The Shot evidence grammar remains deliberately narrow. CAP review still requires an explicit verified Story→Scene ledger association; no inference solely from IDs.
- No claim of end-to-end UI acceptance until the actual copied project is inspected.

## Commands
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_19a_governed_plan_adapter.py tests/test_phase_20_19_3b5_19a_story_scene_authority.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
