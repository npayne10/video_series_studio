# Phase Q3.1.3.2 — ReferencePlan Provenance Integration

Status: **read-only report committed; awaiting local validation**. No production compiler or UI wiring.

The source is an already compiled `CompiledProductionPackage.reference_plan` object and an independently supplied, governed `ProviderReferenceCapacityProjection`. The report checks that ReferencePlan passed, that all IDs and roles/priority values are valid, that eligible direct references match the supplied projection (including required first and provider-ready preferred), and that no extra direct reference is silently accepted. Non-direct roles and optional or non-ready preferred references do not occupy direct H3 capacity. Full-shot plans that have additional future direct references fail closed until a span-scoped authority is supplied; no guessed temporal activation.

The report preserves the source package fingerprint, compiled package fingerprint, provider profile fingerprint, SHA256 digest of exact compiled ReferencePlan JSON, original eligible reference IDs, and a deterministic combined report fingerprint. It delegates precedence verification to the previously tested Q3.1.3.1 review, and returns recommendations without making changes.

**Scope boundary:** this is a source-to-proposal review, not operator approval, source verification against the latest on-disk package, provider execution, or a persisted audit log. Caller-supplied projection must originate from governed provider policy and current compiled sources. Source package freshness and review workflow must be implemented and tested separately before any production selection changes. No ComfyUI jobs run and no edits to TSR2 production authority.

## Local acceptance

    cd D:\VSCS\video_series_studio
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_reference_plan_provenance.py -v
    python -m pytest -q
    git diff --check

Baseline 2107 passed. Three new cases target 2110 passing. No UI test needed because UI unchanged.
