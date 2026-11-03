# B.5.20 — Contextual Narrative Interpretation

Status: **automated baseline and negative-path operator checks passed**; isolated positive-path integration test committed, awaiting local execution and acceptance. Live-project positive UI acceptance is still outstanding.

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

## Controlled positive-path acceptance (isolated; no project mutation)
- Test: `tests/test_phase_20_19_3b5_20_governed_positive_acceptance.py`.
- The fixture writes disposable planning collections beneath pytest's `tmp_path`, using the real `ProductionPlanningContracts` calculators and production deserializers for Episode, Scene and Shot.
- Two synthetic Shot bindings are marked Ready *inside the isolated fixture only*. This validates the existing governed evidence forwarding and Qt inspection path; it is **not** evidence that real project assets have approved CAPs or references.
- The positive test verifies correct registered-asset relationship display, Shot attribution, advisory-only messaging and unchanged Draft dependencies. Negative tests reject Draft bindings and stale contracts.
- The parser now supports location-first clauses at the beginning of verified labelled narrative fields (`required_action:`, `narrative_purpose:`, `production_objective:`).
- This does not lift the H3 live-generation hold or authorise changing Xorix project asset statuses.
- Once all local quality gates pass, record the resulting test counts and decide whether a separate real-project end-to-end positive UI scenario remains necessary for formal phase closure.

### Operator commands
```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_20_governed_positive_acceptance.py -v
python -m pytest -q tests/test_phase_20_19_3b5_20_contextual_shot.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
