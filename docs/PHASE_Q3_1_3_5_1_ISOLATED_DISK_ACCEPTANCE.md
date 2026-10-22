# Q3.1.3.5.1 — Isolated Persisted-Project Acceptance

Status: **first disk-backed acceptance increment committed, awaiting local verification; full end-to-end sign-off remains open**.

The new tests use pytest `tmp_path` (not `D:\VSCS TSR2`) with a genuine `production/production_packages.json` file read by the actual `ProductionPackageService.list_packages` deserializer. They use the Q3.1.3.5 `H3PersistedAuthoritySource` to check package identity, repeatability, no file mutation, missing package, ambiguous duplicate and replaced ID. The ProductionTask repository is a read-only test stand-in.

These tests **do not** exercise the real JSON ProductionTask repository or a fully governed approved ProductionPackage with all compiler prerequisites. Consequently, they cannot yet establish end-to-end real-source recompilation, span-plan generation, provider-profile freshness or persisted ProductionTask freshness. Those must be added before declaring the entire persisted-project acceptance complete. No UI behavior changes in this increment.

Validation:

    cd D:\VSCS\video_series_studio
    git status --short
    git fetch origin
    git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_persisted_project_disk_acceptance.py -v
    python -m pytest -q
    git diff --check

Prior baseline 2125 passing; four new tests target 2129. No original production files, Shot approvals, QC states, tasks or Episode timeline may be changed.
