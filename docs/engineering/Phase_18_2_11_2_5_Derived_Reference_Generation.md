# Phase 18.2.11.2.5 — Derived Reference Generation

## Purpose

Generate governed production-reference views from the single locked ChatGPT-authored MASTER without allowing VSCS to redefine canonical identity.

## Contract

- A locked MASTER is mandatory.
- The MASTER image path is part of every provider request.
- MASTER itself is never a selectable derived view.
- Operators explicitly select the views to generate in this phase.
- Category-specific required-view templates are deferred to Phase 18.2.11.2.6.
- Every generated output is registered as a structured canonical reference and production-library entry.
- Every derived entry has origin `VSCS_DERIVED` and parent linkage to the current MASTER.
- Generated outputs enter lifecycle `Candidate`; human review remains mandatory before approval/locking.
- An active view cannot be generated twice without first retiring the existing candidate/reference.

## Provider architecture

`DerivedReferenceGeneratorRegistry` provides a replaceable generator boundary. Providers expose a name, production-capability flag and a `generate()` method receiving `DerivedReferenceRequest`, including the MASTER file path.

The built-in `VSCS Offline Derived Preview` provider is deliberately non-production. It reads the MASTER and emits deterministic SVG review cards so the complete workflow can be exercised without external generation infrastructure. Future OpenAI, Flux, ComfyUI or other providers must satisfy the same MASTER-conditioned contract.

## UI

Canonical Profiles exposes **Generate Production References**. The dialog provides manual checkboxes for all non-MASTER reference views plus generator, width, height and seed controls. Successful generation creates Candidate references and refreshes the CAP list.

## Deferred

- category-specific required/optional reference templates
- one-click Generate Missing Required Views
- production image-conditioned provider implementations
- readiness scoring/gates
- automatic prompt/reference selection for Production Planning
