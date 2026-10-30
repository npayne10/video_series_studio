# Phase 20.19.3B.5.19 — Context-Aware Narrative Relationships & Shot-Level Evidence Integration

Status: **Initial Shot evidence contract and safe UI slice committed; full source integration and contextual language resolution NOT complete.** Local Windows checks and UI acceptance pending.

## Implemented
- Typed `ShotSpatialSource` explicitly binds `shot_id`, `story_id`, `text` and asset IDs, and `ShotSpatialFinding` retains Shot/Story IDs, verbatim excerpt and source character offset.
- `inspect_shot_spatial_evidence` reuses the B.5.18 name-based resolver only for actual supplied Shot text, registered assets bound to that Shot, and the selected Story. A Shot binding alone is **not** spatial evidence; empty Shot text produces an unresolved finding.
- Operator action **Review Shot Spatial Evidence (Offline)** in the Story CAP Draft form. The action is read-only by default, requires explicit confirmation before appending supported `contains` lines, and retains the pre-existing Draft-only review cache.
- Until a verified, project-scoped Shot text reader is wired, the UI reports **No verified Shot text reader connected** and does not invent Shot relationships.
- Unit and UI tests cover provenance, empty text, binding isolation, Story identity isolation, and unavailable reader behavior.

## Not yet delivered
- No authenticated connection from current persisted Shot records to `ShotSpatialSource` has been implemented. Existing `planning/asset_resolutions.json` bindings do **not** prove that any Shot prose is available. Mapping a text field without examining its provenance/schema would risk falsely attributing evidence.
- No context-aware extraction of `against the forward bulkhead`, pronouns, implicit containment, proximity or anchor constraints has been implemented yet. This increment extends evidence handling and exposes truthful absence, rather than pretending complete context awareness.
- No paid providers, geometry inference, Canon promotion, image/video generation, CAP edits, H3 execution, or audit file changes.

## Verification
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_19_shot_spatial_evidence.py tests/test_phase_20_19_3b5_19_shot_spatial_dialog.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## Operator acceptance
Open **Canonical Profiles → Story → CAP Batch Review → Review Cached Proposal**, then click **Review Shot Spatial Evidence (Offline)**. Unless an authorized Shot text source has been supplied, the dialog must explicitly state that no verified reader is connected. No relationship should be appended and no CAP persisted. Positive source cases are covered by synthetic tests, without mutating the Golden Path audit.

## Next integration prerequisite
Identify and verify the repository's canonical persisted Shot description/text API, Story-to-Shot relation, and asset-binding schema, then connect only authoritative text with fingerprint/freshness checks. Afterwards extend the text grammar using grounded location/fixture anchors and source-ambiguity review. Preserve the H3 live hold.
