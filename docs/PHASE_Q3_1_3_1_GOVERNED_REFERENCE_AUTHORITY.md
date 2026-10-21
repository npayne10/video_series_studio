# Phase Q3.1.3.1 — Governed Reference Authority Integration

Status: **read-only projection review implemented**; not installed in active production compiler or UI. No production-state or media changes.

## Source authority

Existing `project_provider_reference_capacity` in `application/provider_reference_capacity.py` remains the provider-aware reference authority. It classifies governed priority REQUIRED and PREFERRED, excludes non-direct roles, checks capacity, selects REQUIRED first, then provider-ready PREFERRED in governed order, and reports deferred preferred references. `SpanScopedProviderInputCompiler` separately creates exact picture slots with IDs, paths and semantic labels; the H3 span adapter/compiler carries authoritative slots and guide checks into jobs.

## Q3.1.3.1 implementation

`h3_governed_reference_review.review_governed_h3_references` accepts a previously compiled `ProviderReferenceCapacityProjection`, explicitly typed `H3ReferenceCandidate` records from an authoritative caller, and an operator-asserted set of guide overlaps. It verifies the existing direct projection is executable, required references and capacity are preserved, IDs and required flags are consistent, and projected slot order matches the existing required/preferred precedence. It fails closed on mismatches.

It produces an immutable review record with a deterministic authority fingerprint, current governed selected/deferred IDs, and *possible* differences between advisory selection and active slots. Guide overlap is NEVER inferred from picture contents. Deferment remains a proposal requiring human review; **no edits to approved ReferencePlans, SpanScoped inputs, H3 jobs, ProductionTasks, Shot status, QC, or Episode assets are made**.

This is the first read-only reconciliation increment, not a production integration of selection. Future work must map actual governed roles and guide metadata into candidates, bind source-plan/package fingerprints explicitly, present proposals to the operator, and require an approval mechanism before any new plan or job can be compiled. Existing span adapter and provider executor were not modified.

## Validation

    cd D:\VSCS\video_series_studio
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_governed_reference_review.py -v
    python -m pytest -q
    git diff --check

Previous known full-test baseline: 2101 passing tests. Five new cases should make 2106 if everything passes.

## Governance boundary

Original project D:\VSCS TSR2 is unchanged, as are SHT-003 pending QC, approvals, scheduling, generated media, assembly and Picture Lock. No ComfyUI render is scheduled by this phase.
