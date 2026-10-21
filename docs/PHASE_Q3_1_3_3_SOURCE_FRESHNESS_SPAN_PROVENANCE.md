# Phase Q3.1.3.3 — Source Freshness & Span-Specific Provenance

Status: read-only validator and six tests committed; **local acceptance pending**.

## Authority and freshness contract

`validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)` takes two compiled packages, one representing the recommendation's source and one **independently refreshed by the caller** through existing approved source authority. The function cannot certify that a caller actually refreshed the source from disk. It compares compiled-package fingerprints, source-package fingerprints, Shot identity, and the exact canonical JSON digest of the governed ReferencePlan; mismatches reject the review.

The function also checks that the span plan's package fingerprint is the same, and that the execution span fingerprint references that plan. Only the exact matching span's active direct slots are examined; future-only Shot references are excluded. The chosen provider reference slots and deferred references must cover the active set exactly and match the supplied provider capacity projection. Existing reference priority precedence and human guide-overlap review remain governed by Q3.1.3.1.

It returns an immutable advisory report with package, ReferencePlan, span-plan and provider-profile fingerprints. It does NOT recompile the source package, persist approvals, change reference sets, modify the existing H3 compiler, launch ComfyUI or touch the original TSR2 project.

## Follow-up integration gate

Before execution-affecting integration, the caller must prove that the refreshed package came from a separately recompiled, *latest approved* production source and that its fingerprints and plan IDs match authoritative persisted data. The span-input plan itself should be independently recompiled from the refreshed package (`SpanScopedProviderInputPlan.require_source`) and fresh provider profile policy verified. The new validator does not substitute for these requirements.

## Local tests

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_span_freshness_provenance.py -v
    python -m pytest -q
    git diff --check

Previous baseline 2110 passing; six additional tests target 2116 passing. No UI test because UI unchanged.
