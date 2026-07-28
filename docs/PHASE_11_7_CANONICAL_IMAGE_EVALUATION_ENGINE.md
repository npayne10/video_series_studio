# Phase 11.7 — Canonical Image Evaluation Engine (CIEE)

## Purpose

CIEE v1.0 provides deterministic local quality-control checks for canonical image references before they are approved for production.

## Evaluation flow

```text
Canonical image candidate
        ↓
CIEE local technical evaluation
        ↓
Score + decision + warnings
        ↓
Manual semantic/canon review
        ↓
Approve, revise, or regenerate
```

## Technical metrics

CIEE v1.0 evaluates:

- image decoding and file integrity;
- width, height, and total resolution;
- average exposure;
- luminance contrast;
- highlight and shadow clipping;
- sampled local edge/detail variation;
- suitability of the aspect ratio for common VSCS formats.

The engine returns one of three recommendations:

- `PASS`
- `REVIEW`
- `REGENERATE`

## Deliberate v1.0 boundary

CIEE v1.0 does not claim to understand the semantic content of an image. Prompt adherence, visible text, identity consistency, anatomy, engineering plausibility, and canon consistency remain clearly listed manual checks. A future vision-provider adapter can implement those checks without replacing the local evaluator.

## CAP editor integration

Select an image in the Canonical Reference Gallery and click:

```text
Evaluate Selected Image…
```

The report is displayed and stored under:

```text
<Project>/Canonical Assets/<ASSET-ID>/.metadata/evaluation/<IMAGE>.ciee.json
```

The report includes the engine version, asset category, technical scores, overall recommendation, warnings, and category-specific manual review requirements.

## Initial category review guidance

Category-specific manual checks are included for ships, characters, locations, and planets. Other categories receive the common production-review checklist.

## Validation

```powershell
python -m compileall src
pytest
```
