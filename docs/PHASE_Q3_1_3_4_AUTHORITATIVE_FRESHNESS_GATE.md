# Phase Q3.1.3.4 — Authoritative Source Recompilation & Freshness Gate

Status: **read-only callable gate implemented; local validation pending.**

`verify_current_h3_reference_authority` accepts an explicitly supplied `load_current_source` callback that must retrieve the currently approved ProductionTask and ProductionPackage using caller-owned authoritative repositories. It rejects missing reference roots, task/source Shot identity mismatches and unreadable or invalid sources. It invokes the existing `ProductionPackageCompilerService(reference_root=...).compile(task, source, profile=original.profile)`, then compiles the span inputs from the refreshed package, then calls `validate_h3_span_freshness` for the requested execution and capacity projection.

This gate cannot independently verify that the callback actually fetched the latest source; integration with concrete task/package repositories, revalidation of profile authority, and independently refreshed span-input lineage remain subsequent requirements. It is **not wired into production execution**. The current span-input validator expects the caller execution's source-span fingerprint to match the freshly compiled span plan and fails closed on mismatches. No saved production document, ReferencePlan, task, QC, or media is changed.

## Local acceptance

    cd D:\VSCS\video_series_studio
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_authoritative_freshness_gate.py -v
    python -m pytest -q
    git diff --check

Prior baseline 2116 passing, four additional cases target 2120. These focused tests use an injected fake compiler to verify call ordering and failure behavior, **not real persisted project authority**. Future tests should use a disposable acceptance project and real source repositories, without touching D:\VSCS TSR2.
