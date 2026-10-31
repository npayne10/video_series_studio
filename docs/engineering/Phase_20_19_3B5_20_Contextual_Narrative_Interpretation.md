# B.5.20 — Contextual Narrative Interpretation

Status: Initial **offline, advisory-only** implementation; quality gates and operator acceptance pending.

## Intent
Interpret additional explicit spatial language from verified governed Shot narratives without promoting unverified text, guessed assets, or Draft bindings into CAP authority. This slice supports named assets in propositions such as “Diagnostic Console remains inside Engineering Control Room” and location-first clauses such as “In the empty engineering control room, the diagnostic console maintains a steady blue glow.” It is intentionally narrower than a full natural-language understanding engine.

## Safety and sources
- Uses the existing `ShotSpatialSource` contract after upstream planning authority checks.
- Requires matching approved Story ID, both exact registered asset names, and both Shot-bound asset IDs.
- Rejects duplicate-name ambiguity and unsupported relationships. No text-only asset invention.
- Returns `ContextualShotSuggestion` with `confidence=review_required`; never writes CAP dependencies, Canon, approval or reference images.
- The UI has a separate **Inspect Contextual Shot Suggestions (Offline)** button in `StoryCAPSpecificationDialog`. It displays source-scoped suggestions using an information dialog and makes no changes.
- The existing **Review Shot Spatial Evidence (Offline)** remains separate and retains explicit operator confirmation.

## Scope not yet implemented
- Location-first narration is recognised only when both exact registered asset names are present in the same qualifying clause and both are bound to the verified Shot. Broader coreference, paraphrase, indirect implicit relationships and multi-sentence spatial context are not implemented.
- Verified Shot availability still requires Ready bindings and recomputed production-planning contracts. The disposable Golden Path audit binds assets at Draft and will correctly lack authoritative Shot sources.
- Positive end-to-end production UI acceptance not completed.

## Standard checks
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_20_contextual_shot.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
