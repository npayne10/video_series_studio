# Q3.1.3.5.1b — Both Persisted Repositories, Isolated Acceptance

Status: initial two-repository disk acceptance tests committed; **end-to-end source recompilation acceptance remains open**.

These tests use genuine `JsonProductionTaskRepository.get` and `ProductionPackageService.list_packages` against files created under pytest `tmp_path`. They verify exact IDs, no change to either JSON file, changed task Shot identity, replaced package identity, and missing task. They never use `D:\VSCS TSR2`, and never modify existing approved media, QC, task or Shot state.

The next indispensable acceptance checkpoint is integration against a *fully valid, governed, approved* ProductionPackage fixture meeting `ProductionPackageCompilerService.compile` prerequisites; then compile a temporal span and feed its real H3 execution plan through `verify_persisted_h3_reference_authority`. The minimal JSON records in these tests intentionally have insufficient fields for valid recompilation. The full recompilation, policy provenance, and stale-authority paths are **not proven by these tests**.

Local commands:

    cd D:\VSCS\video_series_studio
    git status --short
    git fetch origin
    git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_persisted_both_repositories_acceptance.py -v
    python -m pytest -q
    git diff --check

Baseline 2129 passed; four new tests target 2133.
