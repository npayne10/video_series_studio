# Phase 20.19.3B.5.11 — Anchor placement and collision validation

Status: Initial increment committed; Windows quality gates and operator acceptance pending.

## Implemented
- `AnchorPlacement` identifies a parent anchor and child anchor with a typed millimetre offset (default zero).
- `place_at_anchor` translates child-local geometry into the parent coordinate frame by aligning named anchors, preserving fixed dimensions. Missing anchors return explicit findings instead of guessing.
- CAP dependency constraints optionally persist anchor placement as a Draft attribute; the Story CAP form accepts an optional fifth `parent>child` segment after existing four pipe-separated relationship columns.
- For `contains` relationships with both geometries present, the continuity validator resolves the placement before deterministic bounding-box containment.
- `missing_anchor` blocks Draft preflight, along with existing frame mismatch and out-of-bounds conditions.
- `check_collision` detects positive-volume overlap between two AABBs in a common frame. Touching surfaces are allowed. Four new focused tests cover alignment, absent anchor, overlap and incompatible frames.
- No OpenAI call or CAP approval is involved. H3 live generation remains on hold.

## Deliberate limitations
- Translation only: no rotation, scale, anchor orientation, or arbitrary frame transform hierarchy.
- Named anchor positions are local offsets from each geometry origin. Cross-frame alignment is achieved only when the operator supplies an explicit parent/child anchor pair. Anchor identity and physical correctness are **not** independently proven.
- The collision function is currently a pure local validator and is **not wired into a multi-asset sibling collision graph**, because the Draft dependency contract does not yet contain a complete set of sibling placements. It must not be advertised as comprehensive scene collision prevention.
- Existing four-column dependency lines remain valid. The optional fifth column uses `parent>child`, without offset editing in the Story UI.
- Missing target CAP geometry remains unverified; this is not proof of clearance.

## Acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_11_anchor_placement.py tests/test_phase_20_19_3b5_10_typed_geometry.py tests/test_phase_20_19_3b5_10_geometry_dependency.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
UI: use a cached CAP proposal; the optional fifth relationship column accepts `CAP-PRP-001|contains|forward bulkhead|900|mount>base`. Do not claim valid physical placement until both asset geometries and anchors exist. Cancel without persistence. Do not spend money on paid regeneration.
