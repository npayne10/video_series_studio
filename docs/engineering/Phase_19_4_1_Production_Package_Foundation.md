# Phase 19.4.1 — Production Package Foundation

## Objective

Establish the canonical, provider-independent production-intelligence contract that all later Phase 19.4 compilers enrich and from which provider-specific prompts are eventually derived.

## Input boundary

The only authoritative input is the current immutable `IntegratedPlanningPackage` produced by Phase 19.3.9 after Planning Review approval.

## Canonical sections

`ProductionPackage` reserves explicit sections for:

- provenance;
- story context;
- Shot authority;
- assets and canonical references;
- camera;
- lighting;
- environment;
- action and performance;
- continuity;
- style;
- dialogue;
- effects;
- references;
- universal production description;
- provider outputs; and
- validation.

Phase 19.4.1 populates only data already governed by Phase 19.3. Action/performance, continuity, style, dialogue, effects, UPD and provider outputs remain empty rather than being guessed.

## Persistence and history

Packages are stored project-locally in `production/production_packages.json`, schema version `1.0`. Materialization from identical current planning is idempotent. A changed Integrated Planning Package produces a new Production Package while preserving prior packages as history.

## Staleness

A Production Package is current only while its `source_fingerprint` matches the current Phase 19.3 Integrated Planning Package. If Planning becomes stale, no Production Package is current. Phase 19.4 compilers must therefore consume `require_current_package()` rather than selecting historical packages directly.

## Ownership boundaries

Phase 19.4.1 does not author story action, dialogue or performance; compile prompts; choose providers, models or workflows; add renderer parameters; or duplicate planning decisions. Its purpose is to create the stable heart into which later specialist compilers place production intelligence.

## Acceptance criteria

- deterministic package identity and fingerprint;
- exact Phase 19.3 provenance;
- provider-neutral canonical schema;
- idempotent materialization;
- historical preservation after planning changes;
- current/stale resolution through Phase 19.3 fingerprinting;
- empty specialist sections where authority does not yet exist;
- atomic project-local persistence;
- Ruff, format, mypy, pytest and coverage gates green.
