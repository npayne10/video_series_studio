# Phase 11.7.3 — Regenerate from Evaluation Feedback

## Purpose

Phase 11.7.3 closes the canonical-image quality loop by converting the latest PRE and SIEE findings into explicit CAIE prompt refinements and generating a new XCIC Candidate.

## Workflow

1. Generate a canonical Candidate.
2. Run CIEE technical evaluation.
3. Run SIEE semantic evaluation.
4. Run PRE combined production-readiness evaluation.
5. Select the evaluated Candidate.
6. Click **Regenerate from Feedback…**.
7. Review the consolidated corrections and confirm.
8. VSCS creates a new Candidate while preserving the original image and reports.

## Feedback sources

The regeneration action reads:

- `<image>.pre.json`
- `<image>.siee.json`
- `<image>.generation.json`

It merges PRE recommendations, SIEE recommendations and detected SIEE violations, removes duplicates and passes the resulting correction set to CAIE.

## CAIE refinement

CAIE v1.1 appends an evaluation-driven correction section after the canonical facts and production constraints. Feedback refines presentation only and is explicitly prohibited from introducing new canon.

## Render behaviour

The previous model, dimensions and negative prompt are retained. The seed is incremented to produce a new variation. XCIC Core and ComfyUI perform the render through the existing canonical generation pipeline.

## Lineage and auditability

The new generation manifest records:

- `generation_mode: evaluation_feedback`
- `refinement_instructions`
- `parent_reference_id`
- `parent_generation_manifest`

The original Candidate remains unchanged, enabling side-by-side comparison and evaluation-history tracking.

## User interface

The CAP editor adds **Regenerate from Feedback…**. It is enabled only when the selected image has PRE, SIEE and generation metadata available.

## Files

- `src/vscs/application/caie/models.py`
- `src/vscs/application/caie/engine.py`
- `src/vscs/application/caps/asset_generator.py`
- `src/vscs/presentation/widgets/cap_reference_regeneration.py`
- `src/vscs/main.py`
- `tests/unit/test_feedback_regeneration.py`
