# Phase 20.19.3B.5.17 — Story-Evidence Spatial Extraction & Coordinated Asset Proposal Planning

Status: First conservative, offline implementation committed to GitHub. Local Windows gates and operator UI acceptance pending.

## Implemented
- A read-only evidence extractor for explicit registered asset-ID location statements of the form `CAP-PRP-001 is located in CAP-LOC-001` or `CAP-PRP-001 inside CAP-LOC-001`. The source is exclusively the **approved/locked Story description** already fingerprint-checked by `StoryCAPBatchService.current_story_fingerprint`.
- Each finding carries the Story ID, exact excerpt, character offset, parent and child asset IDs and evidence kind. Unknown/unregistered IDs and vague prose are **not** interpreted as relationships.
- A coordinated plan for the selected parent aggregates explicit child evidence and existing parent dependencies, then identifies which parent/child assets still lack typed geometry. The plan does not invent dimensions, anchor positions or clearance.
- **Review Approved Story Spatial Evidence (Offline)** in the existing Draft CAP form shows evidence and missing geometry. Only an explicit operator Yes appends unapproved `contains` relationships to the form. Existing dependencies are retained; Save Review & Continue uses the already accepted unapproved proposal cache.
- Focused regression tests cover source offsets, unknown IDs, missing geometry, conservative empty results and UI consent.

## Important limitations
- Approved Story **description**, not full manuscript text or arbitrary Shot prose. The description may be short or omit explicit asset IDs. No natural-language entity resolution, automatic character/location association or complex relation extraction has been implemented. A zero-evidence result must not be reported as completed scene discovery.
- Scene/Shot binding registry is used only to delimit known registered asset identities in this increment; no unsupported narrative-to-asset mapping is assumed.
- Stored CAP metadata remains the source for geometry. No new geometry measurements are inferred.
- This is an initial incremental slice of B.5.17, **not** completion of coordinated planning across all scene assets. Multi-parent coordination, Shot-level provenance, spatial conflict resolution and optional cost-confirmed AI completion remain future work.
- Zero provider requests, no user audit file modifications, no CAP/canon writes from the evidence action, no image/video generation; H3 live hold remains in force.

## Verification
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_17_story_spatial_evidence.py tests/test_phase_20_19_3b5_17_story_spatial_evidence_dialog.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## Operator UI review
Open approved Story → CAP Batch Review → Review Cached Proposal for the Engineering Control Room. Click **Review Approved Story Spatial Evidence (Offline)**. If the approved Story description has no explicit registered asset-ID relationship, the result should list no candidate relationships, show missing typed geometry and leave the dependency field unchanged. This is expected. For a positive controlled test, use unit tests, not edits to the Golden Path audit Story. No paid Generate / Regenerate Using AI and no final CAP persistence are needed.
