# ADR-0034 — Phase 19.5.11 AI Review, Gap Detection & Repair Suggestions

## Decision

Phase 19.5.11 introduces a read-only review layer over the current Story revision's automation proposal graph.

Deterministic checks identify objective gaps first: unresolved canonical assets, missing Shot specialist proposals, rejected specialist proposals, and explicit continuity conflicts. AI may improve the wording or contextual usefulness of a repair suggestion, but AI is never an approval authority and never applies the repair.

## Governance

The review layer MUST NOT:

- accept or reject proposals;
- create or modify canonical assets, CAPs or Master References;
- mark governed plans Ready;
- overwrite human-governed authority;
- compile production packages;
- approve production;
- submit provider/render jobs.

Repairs remain explicit follow-up actions through existing VSCS services. Existing functions are reused and extended rather than replaced.

## Rationale

Gap detection benefits from deterministic inspection wherever VSCS already has explicit contracts. AI is useful only for advisory interpretation and repair suggestions where contextual explanation adds value. This preserves continuity, automation consistency, provenance and human authority.
