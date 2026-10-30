# Phase 20.19.3B.5.19a — Authoritative Shot Text Integration & Evidence Freshness

Status: **Partial implementation committed.** Local Windows tests and operator review pending. Shot-to-Story linkage is not yet established.

## Verified canonical source
- `ShotPlanningService` in `src/vscs/application/shots/service.py` persists production Shots in `<project>/story/shots.json`.
- `ProductionShot` in `application/shots/models.py` contains `shot_id`, `scene_id`, `description`, `blocking_notes`, `continuity_notes`, `subject_asset_ids` and `required_asset_ids`.
- `StoryService` persists `<project>/story/scenes.json`, but its Scene model/serialization does not establish a verified `STORY-001` lifecycle identifier on each scene. A matching episode or scene ID is **not** proof of an approved Story association.

## Implemented
- Added `authoritative_shot_text.py`: a read-only `ShotTextReader` protocol compatible with the existing `ShotPlanningService.list_shots`; explicit `VerifiedStorySceneScope` requires Story ID, approved fingerprint, verified Scene IDs and source provenance.
- `capture_authoritative_shot_text` builds a deterministic SHA-256 evidence snapshot from persisted selected Shot descriptions, blocking/continuity notes and bound assets, without writing any project data.
- `assert_shot_text_fresh` re-reads current Shot source and refuses stale Shot content, changed Story fingerprint, changed scope or mismatched metadata.
- When verified Shot/Story scope cannot be supplied, the UI says which authority is absent and does **not** present arbitrary Shots as Story evidence.
- Regression tests cover available Shot text, stale Shot revisions, stale Story authority, wrong scenes and missing scope.

## Scope limits
- An authenticated, persisted Story-to-Scene association **still needs integration**, so this phase is not complete and existing CAP review cannot yet safely pass live Shot text to the Shot spatial analyser.
- The new snapshot API works with an explicit verified mapping; the current UI does not manufacture that mapping. It deliberately fails closed.
- No new paid provider calls, Canon promotions, H3 video execution, CAP image generation, project writes or audit changes.

## Operator acceptance
1. Pull the branch, run quality gates and restart VSCS.
2. Open cached Story CAP Draft and click **Review Shot Spatial Evidence (Offline)**. Expect a message identifying `story/shots.json` as the known Shot source but refusing unverified Story-to-Scene association.
3. Positive freshness tests run exclusively with synthetic Shot objects without editing Golden Path.

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_19a_authoritative_shot_text.py tests/test_phase_20_19_3b5_19_shot_spatial_dialog.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
