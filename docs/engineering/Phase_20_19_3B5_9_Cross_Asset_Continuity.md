# Phase 20.19.3B.5.9 — Structured Cross-Asset Dependencies & Continuity Validation

Status: Initial implementation in GitHub; local Windows acceptance pending.

## Implemented
- Explicit, typed Draft CAP relationships: `contains`, `mounted_in`, `adjacent_to`, `located_in`, `references`.
- Persistent dependency records on the existing structured CAP metadata envelope. Each record identifies the registered target CAP asset, relation, optional fixed anchor, and optional minimum clearance in millimetres.
- Operator review UI includes a separate cross-asset relationship input (one line: `CAP-PRP-001|contains|forward bulkhead|900`). The example is **not** automatically asserted to be Story canon.
- Read-only cross-asset validation uses the current project's registered asset service and stored CAP specifications. It reports missing targets, undeclared/duplicate relations, self-dependency, invalid category relations, missing target specification, mismatched target category, and unverifiable dimensional clearance.
- Hard identity and relationship failures prevent Draft CAP persistence. Absence of a target CAP specification and incomplete geometry are explicitly advisory, *not proof* of physical consistency.
- Six unit tests exercise valid location-console relation, missing links, cross-project missing assets, missing target specification, clearance geometry warning, and self-dependency.

## Boundary
This phase does **not** implement a geometric solver or prove that a console physically fits a room. It does not infer cross-asset relations from AI story descriptions. Physical dimension and placement consistency should be evaluated against a future canonical typed geometry reference schema and source evidence.
No generated proposal, dependency, missing-target note, or operator Draft approval constitutes approved Story Canon.
No OpenAI calls are required for validation; persistent cache and paid-generation gate remain unchanged.
H3 live video generation remains on hold.

## Local acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_9_cross_asset_continuity.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI acceptance: Review a cached control-room proposal without contacting OpenAI. In cross-asset dependencies enter `CAP-PRP-001|contains|forward bulkhead|900` only for inspection; verify it is parsed and Draft-only. Cancel all dialogs in Golden Path audit. No paid regeneration or CAP creation is necessary. The user-owned untracked architecture audit must remain untouched.

## Review preflight acceptance increment
The Batch Review dialog now invokes `validate_reviewed_dependencies` locally after operator confirmation of the Story CAP Draft form and **before** proceeding to CAP Detail Decisions. An unknown project asset, incompatible relationship or invalid identity raises a visible error and cannot reach the Draft save step. A missing target specification or unmeasured clearance shows an advisory, explicitly **unverified** notice; physical fit is not asserted.

No paid OpenAI request is made by dependency preflight. For manual acceptance, use the existing cached `CAP-LOC-001` proposal. First enter `CAP-PRP-999|contains|forward bulkhead|900` and click the Story Draft form's Save: expect the batch to reject the unknown target, with no saved CAP. Then reopen cached review and enter `CAP-PRP-001|contains|forward bulkhead|900`: expect the independent registered Diagnostic Console to be accepted as a relationship target but missing specification/unmeasured geometry clearly marked as unverified. **Cancel at CAP Detail Decisions** instead of persisting the CAP. Neither test needs OpenAI or the paid regeneration button.

New regression tests: `tests/test_phase_20_19_3b5_9_review_preflight.py`.
