# Phase 20.19.3B.5.6 — Design quality and cross-asset continuity

Status: Initial increment committed; local Windows tests and live UI acceptance pending.

## Implemented
- OpenAI's advisory CAP design prompt now requests spatially stable, camera-independent physical geometry, proposed dimensioned scale and independent identity for related props/ships/characters.
- New pure `assess_design_quality` checker flags camera-relative prose, unmeasured scale, imprecise layout and a missing functional console/workstation anchor in Location proposals. These are **advisory** warnings, not proof that remaining content is physically correct.
- `StoryCAPProposal.quality_issues` carries warnings in memory; field-level review shows them in the enlarged rationale box, prefixed QUALITY REVIEW. All decisions remain Defer until explicit operator selection. No image or video generation.
- Five focused tests added.

## Known boundaries
- Cross-asset links are guided by a provider instruction, **not** a resolved CAP dependency graph. No guarantee of consistency or asset-level conflict detection with the separate Diagnostic Console CAP yet.
- The location-specific functional anchor warning assumes a console/workstation. It is deliberately scoped to Location candidates in this initial test workflow but may overflag other locations; category subtypes and approved Story evidence need to replace this heuristic.
- Quality checks cannot verify measurement accuracy or physically simulate layout. No actual geometry coordinates, structural design schema, or source-span evidence verification is introduced.
- No canonical promotion and no changes to H3 live-generation hold.

## Acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_6_design_quality.py tests/test_phase_20_19_3b5_5_provider_design.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI: disposable Episode Audit → Story CAP Batch → Engineering Control Room → generate → next review → examine suggested details and advisory QUALITY REVIEW warnings. Cancel rather than save. Note additional OpenAI API cost. Preserve untracked architecture audit.
