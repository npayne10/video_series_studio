# ADR-0029 — Canonical Entity & Asset Resolution Automation

## Status

Accepted

## Context

Phase 19.5 automation must preserve production continuity by resolving Story entities to existing canonical production assets wherever possible. VSCS already has two authoritative capabilities that must remain the source of truth:

1. Story Analysis performs provider-neutral entity extraction and deterministic matching against the project XPD asset catalogue.
2. Asset Resolution verifies an Asset against its approved XPD record, Canonical Asset Profile (CAP), and approved canonical references.

A separate AI-driven canonical matching system would duplicate these authorities and could silently create alternate versions of characters, ships, locations, props, technology or environments.

The active XPD catalogue can also change after Story Analysis was cached. Importing or synchronising canonical assets must therefore not require a second AI Story Analysis call merely to refresh identity matching.

## Decision

Phase 19.5.5 introduces `CanonicalEntityAssetResolutionAutomationService` as a deterministic proposal layer.

For each current Story entity candidate it:

- preserves the cached semantic entity extraction and source evidence;
- re-runs only the existing deterministic entity-name/category matching algorithm against the current XPD catalogue;
- resolves exact existing matches through `AssetResolutionService` with approved Asset, CAP and canonical-reference requirements;
- records the current Asset/CAP/reference dependency fingerprint when resolution succeeds;
- records Partial or Unresolved canonical diagnostics when an existing XPD asset is incomplete;
- emits a reviewable `ASSET` `AutomationProposal` for new, uncertain or possible-duplicate entities;
- never creates or updates an Asset record;
- never generates or approves a CAP;
- never generates or approves a Master Reference;
- never marks any governed asset binding Ready;
- never approves production authority.

Canonical identity is therefore deterministic. AI may have proposed the semantic entity, but AI does not choose the canonical production asset.

## Current-XPD rule

Phase 19.5.5 must not trust a cached entity `match_kind` as final canonical truth. Before producing an Asset proposal, the entity is re-matched against the current XPD catalogue without rerunning AI semantic analysis.

This permits the following safe workflow:

Story Analysis → import/synchronise XPD → Resolve Assets

without paying for or introducing drift through another AI Story Analysis pass.

## Review

Phase 19.5.5 uses the existing Phase 19.5 Proposal Review surface. Asset proposals are displayed under a `Canonical Entity & Asset Resolution` group with full proposal content, canonical diagnostics, provenance and dependency metadata.

The review surface remains read-only in this phase.

## Consequences

- Existing characters such as James Spence can resolve to the same XPD/CAP/Master Reference authority whenever that authority is present in the active project catalogue.
- Newly discovered Story entities remain explicit proposals and cannot silently become canon.
- XPD/CAP/reference changes are fingerprinted for future stale-state detection.
- The clean VSCS TSR test project remains valid: if Xorix XPD assets are not yet available to the active project, the entities correctly remain new/ambiguous proposals rather than being guessed.

## Non-goals

Phase 19.5.5 does not import an external XPD workbook automatically, create canonical assets, generate CAPs, generate Master References, bind assets to governed Shots, or approve production use. Those operations remain separate human-governed workflows or later automation phases.
