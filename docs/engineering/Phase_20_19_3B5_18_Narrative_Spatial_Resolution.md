# Phase 20.19.3B.5.18 — Narrative Entity Resolution & Evidence-Grounded Spatial Relationship Discovery

Status: Initial conservative offline increment committed. Automated quality gates and operator UI acceptance remain pending.

## Implemented
- `narrative_spatial_resolution.py` resolves explicit “X is located in Y”, “X inside Y”, and “X within Y” forms from **approved Story description** to project-registered asset **names**, without requiring CAP IDs in manuscript prose.
- Each resolved relation identifies child, parent, Story ID, exact supporting excerpt, source offset, and evidence kind.
- Asset name matches use whole-word boundaries and prefer longest exact name; equal-length duplicate matches are reported as **ambiguous**, never auto-applied. Unknown names and implicit references do not yield spatial relationships.
- The existing Story CAP Draft review now has **Resolve Narrative Spatial Relationships (Offline)**. Only relationships for the current parent are proposed. Operator confirmation is required before appending `contains` lines. Existing lines are preserved; Save Review & Continue uses existing unapproved project proposal-cache persistence.
- Three regression tests cover named extraction with provenance, ambiguity, and no unsupported inference.

## Restrictions / forthcoming work
- Initial strict phrase grammar only, not general-purpose linguistic scene understanding. References such as “the console stood against the forward bulkhead” or pronouns are not resolved. Project asset tags are **not** automatically assumed to be safe aliases.
- The approved Story **description** is still the evidence source, not the full imported manuscript or Shot text. No inferred dimensions or coordinates, no arbitrary alias inference, and no automated Canon decision.
- Ambiguous relations are surfaced for review; operator must resolve source identity in a future controlled workflow rather than the engine selecting one.
- No additional AI calls, CAP writes, image generation, H3 execution, Story editing, or Golden Path audit changes. No modification to the user-owned architecture audit.

## Verification
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_18_narrative_spatial_resolution.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## UI acceptance
Open **Canonical Profiles → Story → CAP Batch Review → Review Cached Proposal**, then click **Resolve Narrative Spatial Relationships (Offline)**. In the current Golden Path audit Story, no exact named relationship may be present in the approved Story description; if so the expected result is no additions and a list of zero or ambiguous matches, not made-up placements. Validate positive and ambiguous cases through the synthetic tests instead of changing approved project evidence. If a positive candidate is shown, decline once to confirm non-mutation; accept only when intended and cancel later CAP creation.
