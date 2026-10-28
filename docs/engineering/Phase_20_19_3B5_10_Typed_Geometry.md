# Phase 20.19.3B.5.10 — Typed Geometry, Spatial Anchors & Physical Continuity

Status: Initial implementation committed; Windows tests and operator UI acceptance pending.

## Implementation
- Optional `CAPGeometry` stored in existing Draft CAP specification metadata, with mandatory named coordinate frame, operator-provided axis-aligned occupied dimensions in millimetres, origin and unique named anchor positions.
- Strict positive dimensions, unique anchor labels and non-negative clearance values; no generative inference.
- Deterministic local AABB containment: target axis-aligned bounds must lie inside container bounds with the minimum requested clearance on all three axes.
- Mismatched frame IDs and out-of-bounds positions block reviewed Draft persistence. Missing geometry generates an advisory unverified finding when both target CAPs are otherwise available. Missing target CAP remains advisory.
- Optional geometry JSON text editor added to scrollable Story CAP Draft review, requiring operator-supplied numbers. No approval promotion.
- Geometry can be reused from the stored CAP spec; no OpenAI calls and no effect on persistent proposal cache.

## Important limitations
- This is **only an axis-aligned bounding-box validator**, not a structural/collision engine. Arbitrarily rotated objects, doors, walkways, moving envelopes, accessibility, other interior obstacles and mounting mechanics are not modelled.
- Both CAP geometries must use precisely the **same named coordinate frame and shared coordinate origin**. A frame name match is an assertion by the operator, not independently verified physical alignment. Anchor fields currently carry explicit positions, but are **not** used to automatically resolve transforms. Cross-frame transforms and anchor-relative placement are future work.
- Millimetre values are proposed engineering design, not verified Story Canon.
- This feature doesn't create missing target CAPs or authorize images/video. H3 generation remains ON HOLD.

## Test example
A room with `size_mm = (8000,5000,2600)` and `origin_mm=(0,0,0)` can contain a diagnostic console `size_mm=(1500,700,950)` and `origin_mm=(2000,1500,400)` in the same `frame_id`, with 300 mm clearance on all sides. A console placed beyond a room wall is flagged `out_of_bounds`.

## Local acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_10_typed_geometry.py tests/test_phase_20_19_3b5_10_geometry_dependency.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI acceptance: Open cached engineering control-room proposal and confirm optional typed-geometry JSON field is visible, scrollable and editable, with no regeneration. Do not Save the CAP; cancel after reviewing geometry validation. Preserve the architecture audit file.
