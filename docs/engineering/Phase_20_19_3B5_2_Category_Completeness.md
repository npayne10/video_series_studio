# Phase 20.19.3B.5.2 — Detailed category CAP completeness gate

2026-10-26. Status: Initial non-authoritative completeness implementation committed; local Windows tests/UI acceptance pending.

## Implemented
- `application/caps/completeness.py` defines required visual identity categories for Character, Location, Ship, Vehicle, Prop, Technology, Environment, Planet and Uniform. Other types require a generic identity.
- `assess_completeness` lists missing category fields and filled-but-unverified claims. It intentionally **never asserts Master-image readiness**, because no per-claim source evidence or approved canonical reference authority is present in this module.
- `StoryCAPSpecificationDialog` displays missing fields live as operator edits the canonical attribute entries. It continues to permit incomplete Draft saving, subject to existing validation, because completeness is a later promotion gate and not a Draft authoring prohibition.
- Automated tests cover all nine categories, missing fields, fully populated yet unverified generated identity, and reviewed DOCX remaining unverified without claim-level provenance.
- No database migration, provider submission, live image generation or change to existing CAP/reference approval status.

## Critical scope distinction
This phase **does not** yet produce category-complete automatically populated designs. It does not infer dimensional layouts from sparse Story descriptions. Rather, it adds visibility of missing attributes and a fail-closed acceptance boundary so a superficially plausible AI prompt cannot silently become image-ready authority.

Next follow-on: source-span mapped canonical claims vs explicitly marked proposed design decisions, structured AI design proposals for missing fields, review of constraints/dependencies/variants, and a versioned approval-specific promotion evaluator.

## Local tests
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_2_cap_completeness.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI: disposable Episode Audit → Canonical Profiles → Story → CAP Batch → generate Location proposal. Confirm missing field labels are visible (e.g. layout, scale, materials, spatial_anchors, lighting); Cancel and verify zero new CAPs. H3 video hold remains in force.
