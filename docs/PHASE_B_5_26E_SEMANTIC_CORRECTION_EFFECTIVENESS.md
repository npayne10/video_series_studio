# Phase B.5.26E — Semantic Correction Effectiveness and Constraint Enforcement

Date: 2026-11-08
Status: GitHub implementation committed; Windows regression and operator acceptance pending.

## Evidence from B.5.26D

Disposable project `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`; asset `STORY-LOC-A9ED8B387E`.
The first locally corrected supplementary Candidate (reference 2; parent reference 1,
attempt 1/2) rendered and registered successfully. The separately consented semantic
evaluation reported technical 79 versus 82, semantic 58 versus 72, and design
consistency 45 versus 45. The image visibly retained a second door and added
dimension/drafting overlays. The quality report recommended regeneration.

This demonstrates operational success but **not** correction effectiveness. The
remaining local attempt should not be used merely to vary the seed.

## Source audit

- `visual_candidate_regeneration.py` constructs requests from reviewed CAP
  fields; free-form Terra/SIEE findings are advisory-only.
- Previous B.5.26D prompting repeated the base proposal, appended mandatory fields,
  and varied the seed, with no reliable geometric control.
- `VisualCandidateGenerationService` delegates to XCIC/local ComfyUI and
  compares output provenance. It cannot guarantee that a text-to-image model
  obeys count, position, or routing restrictions.
- Saved quality comparison already exposes technical, semantic and design-consistency
  deltas. No new paid evaluation or provider is needed to inspect the trend.

## Implemented bounded safeguards

1. Add a deterministic hard-constraint contract to the correction prompt, using
   reviewed CAP fields only. Exact-one-door language is included **only** when an
   accepted field explicitly describes one door. Count, position, and service-route
   requirements are emphasized but **not** falsely claimed to be machine-enforced.
2. Add explicit negatives for dimension labels, measurement marks, drafting lines,
   arrows, scale bars, watermarks and unwanted access points. These are presentation
   hygiene instructions, not newly approved architectural details.
3. Derive a read-only regression warning from structured saved comparison deltas
   for a regenerated source Candidate. Do not copy untrusted evaluator prose into
   executable prompts. Show this warning in the correction dialog and its existing
   Yes/No confirmation before a new local execution.
4. Preserve the existing two-attempt lineage budget, hash/fingerprint checks,
   candidate-only status, one-image-per-consent rule, and pre-/post-render authority
   checks. No automatic reruns, CAP edits, MASTER promotion, API calls, or GPU work.

## Known limitation and future provider evaluation

Prompting is a probabilistic influence, **not** structural image enforcement.
The current XCIC/local ComfyUI Qwen workflow does not gain deterministic geometry
constraints merely through stronger text. Before claiming geometric conformance,
evaluate provider-compatible controls (layout maps, segmentation/masks, constrained
inpainting or a reference-driven edit pass), compatibility with RTX 5060 Ti 16 GB,
workflow maturity, provenance, and the smallest useful disposable tests. Do not
introduce a new backend without a separate reviewed phase.

## Acceptance

- Ruff lint and formatting; mypy on `src`.
- Focused regeneration and quality tests; full `pytest -q`.
- UI: open the saved failed review of Candidate 2, inspect the warning and the
  grounded correction prompt; cancel the confirmation. Cancel must not render,
  consume an attempt, mutate authority, or invoke Terra.
- Only after inspecting the diagnostics and obtaining fresh operator consent may
  another local Candidate be generated. Never claim the resulting image passes
  without its own visual/semantic review.

The original reference, all saved audits, CAP authority, and the untracked local
architecture audit must remain unchanged.
