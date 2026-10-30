# Phase B.5.19a — Reviewed Story → Scene → Shot authority chain

Status: Initial end-to-end integration committed; Windows quality gates and UI acceptance pending.

## Existing persisted sources
- Approved Story identity and fingerprint: `StoryLifecycleService` plus `StoryCAPBatchService.current_story_fingerprint`.
- Structured Scenes: `StoryService.list_scenes` reads `story/scenes.json`.
- Planned Shots: `ShotPlanningService.list_shots` reads `story/shots.json`. Each Shot has `scene_id`, description, subject/required asset IDs.

## New explicit ownership boundary
- No reliable persisted Scene-to-Story ownership was present in the legacy Scene schema. Added separate project-local `story/story_scene_authority.json` ledger. It stores operator-confirmed Story ID, fingerprint and Scene IDs. No legacy scenes are rewritten or silently assigned.
- **Assign Story Scenes (Reviewed)** in Approved Story → CAP Batch Review accepts only entered persisted Scene IDs; operator confirmation is mandatory. The ledger rejects unknown Scenes, conflicting assignments and stale fingerprints. The existing audit project must **not** be used for positive assignment acceptance without explicit operator intent; use a disposable copy.
- The Batch review verifies Story fingerprint, Scene ownership, reads matching persisted Shot descriptions, and checks evidence fingerprint freshness before passing `ShotSpatialSource` entries to the existing read-only Shot spatial review.
- CAP relationships are proposed only for name-resolved and Shot-bound asset pairs, then require explicit operator acceptance. No automatic CAP creation, Canon approval or provider calls.
- If no association exists, no Shot is passed and the UI reports that the Story-to-Scene association is missing.

## Limitations and safety
- Operator ownership is an explicit governance claim, not a cryptographic proof of original Story authoring. Scene/Shot content can still be changed by other actors; readers must be rechecked after review or at final use. Only Shot description is currently used as spatial prose; blocking/continuity notes are captured in freshness fingerprint but not treated as positional evidence.
- No automatic Scene inference or migrations. The separate ledger remains unapproved ownership metadata, not Story Canon.
- Any real audit project acceptance remains read-only unless the operator deliberately chooses to assign Scenes.

## Tests
- Existing snapshot tests validate changes to Shot text, bindings, Story fingerprint and scope.
- New mapping tests cover persistence, duplicate ownership, stale Story fingerprint, deleted Scene and missing mapping.

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_19a_story_scene_authority.py tests/test_phase_20_19_3b5_19a_authoritative_shot_text.py tests/test_phase_20_19_3b5_19_shot_spatial_dialog.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
