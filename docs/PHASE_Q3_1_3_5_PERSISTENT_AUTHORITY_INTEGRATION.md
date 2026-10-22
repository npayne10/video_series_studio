# Q3.1.3.5 — Persistent Authority Integration & Isolated Acceptance

## Scope
Read-only adapter from VSCS `ProductionTaskRepository.get(task_id)` and `ProductionPackageService.list_packages(shot_id=...)` to the Q3.1.3.4 recompilation gate. The source must match the original task ID, source package ID and Shot ID, with exactly one matching persisted package; missing or contradictory authority is rejected.

The adapter deliberately **does not** call `save`, `materialize`, `persist`, provider execution or any task-state transition. It does not change the existing production compiler, UI, media, ReferencePlan or SHT-003 QC. The supplied ProductionPackageService must be attached to the intended project; use only disposable acceptance projects for non-mocked integration tests.

## Verified versus unverified authority
The module uses actual application repository and service contracts. Its unit tests use isolated in-memory read-only stand-ins and monkeypatch the downstream gate to verify call wiring. This is **not yet** a real on-disk acceptance run and cannot by itself prove freshness of the repository implementation, project binding, or the operator-facing approval flow. A separate isolated on-disk fixture with correctly approved ProductionTask and ProductionPackage records is required before end-to-end sign-off. In addition, these tests do not establish that the profile fingerprint matches a freshly loaded policy registry.

## Local acceptance
    cd D:\VSCS\video_series_studio
    git status --short
    git fetch origin
    git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_persisted_authority_gate.py -v
    python -m pytest -q
    git diff --check

Baseline: 2120 passing tests; five additional focused cases target 2125 passing. No UI workflow has changed, so no UI validation is triggered.

## Subsequent acceptance gate
Create a disposable project outside `D:\VSCS TSR2` (for example `D:\VSCS TSR2 - TEST 4B5` only if it is explicitly confirmed safe to reuse), build genuinely current approved source fixtures using the existing approved test APIs, verify exact on-disk repository read + recompile against matching span and profile policy, and test stale/ambiguous versions. Never advance generated-media QC or Shot state as part of this study.
