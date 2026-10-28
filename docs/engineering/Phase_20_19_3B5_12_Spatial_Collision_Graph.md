# Phase 20.19.3B.5.12 — Multi-Asset Spatial Continuity & Collision Graph

Status: Initial committed increment; Windows acceptance pending.

## Implementation
- `assess_spatial_graph` accepts a Draft parent CAP and a project-scoped CAP specification lookup. It scans explicit `contains` relationships, fetches each child CAP's typed geometry, resolves optional anchor-relative translation into the parent frame, applies parent containment and clearance checks, then tests every fully resolved sibling pair for occupied-volume overlap.
- Returns `SpatialGraphReport` containing all resolved child IDs, per-asset/pair findings and a strict `verified` flag (true only when no findings).
- Missing parent geometry, missing target geometry, missing anchors, out-of-bounds positions, unresolved dependency declarations and overlapping sibling bounds cannot silently be marked verified.
- Draft review preflight now includes graph findings. Detected sibling collisions block progress; missing geometry and other incomplete data remain advisory, with existing single-dependency preflight continuing to block invalid placements.
- No OpenAI generation, no CAP approval, no image or H3 video execution.

## Scope limits
- Axis-aligned bounding boxes only; rigid translations supported through prior named-anchor placement. No rotations, complex shapes, obstacles, doors, swept volumes or dynamic geometry.
- This graph only assesses **explicit declared contained siblings** of one parent. It does not discover implicit project assets, nest arbitrary deep frame hierarchies or guarantee real-world physical compatibility.
- The `verified` field means only that the available typed AABB constraints have no known violations and no missing findings, **not canonical approval or a physics proof**.
- Target CAPs must exist with typed geometry to complete the graph. Missing target CAPs remain advisory in the review path; no synthetic or approved CAP is created.

## Local acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_12_spatial_graph.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI: reuse a previously cached proposal. With only the Diagnostic Console referenced and its target CAP still missing, expect the existing unverified advisory findings. Do not generate new proposals or persist Golden Path records. Sibling overlap acceptance is covered by deterministic tests until two child CAPs with typed geometry exist in a disposable project.
