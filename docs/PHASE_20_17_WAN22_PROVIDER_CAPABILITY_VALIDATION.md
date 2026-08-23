# Phase 20.17 — Wan 2.2 Provider Capability Validation

## Status

Implemented in a dedicated phase branch; local acceptance remains required before closure.

## Objective

Establish a repeatable, provider-neutral mechanism for validating a generation capability against production evidence, using Wan 2.2 as the first concrete provider-edge validation pack.

The architectural rule remains:

> PROVIDERS PRODUCE OUTPUTS. VSCS OWNS GENERATED MEDIA.

Capability validation therefore evaluates evidence already owned by VSCS. It does not grant providers ownership of media, production tasks, approvals, or selection authority.

## Implementation

### Provider-neutral domain

`vscs.domain.provider_capability_validation` defines:

- versioned capability-validation packs;
- scenarios and criteria;
- criterion/scenario outcomes;
- Generated Media evidence references;
- deterministic recommendations;
- separate explicit human approval/rejection.

### Application service

`ProviderCapabilityValidationService`:

- starts a validation session from a registered validation pack;
- requires exact criterion coverage for a scenario;
- verifies every evidence ID exists in the Generated Media repository;
- verifies evidence provenance matches the provider being evaluated;
- computes recommendation without making a governance decision;
- requires complete evidence before accepting a human decision;
- resets a prior human decision whenever evidence changes.

### Persistence

`JsonCapabilityValidationRepository` stores one atomic JSON document per validation session under a caller-selected project repository root. Persistence is deliberately separate from Generated Media and provider registration data.

### Wan 2.2 provider-edge pack

`wan22_video_validation_pack()` defines five required validation scenarios:

1. Text-to-video baseline
2. Image-to-video reference fidelity
3. Camera and motion control
4. Character and subject continuity
5. Complex production shot

Each scenario contains explicit observable criteria. The pack is versioned independently from the provider-neutral validation domain.

### Operator workspace

`ProviderCapabilityValidationWorkspace` provides a PySide6 operator surface for:

- selecting the validation pack;
- starting a provider validation session;
- recording criterion outcomes;
- entering Generated Media evidence IDs;
- adding validation notes;
- displaying the computed recommendation;
- recording explicit approval or rejection with actor identity and reason.

The workspace depends only on the application service boundary. Main-window placement can therefore remain a presentation composition concern without coupling the validation domain to desktop UI code.

## Recommendation rules

| Required evidence state | Computed recommendation |
| --- | --- |
| Any required scenario not run or blocked | `insufficient_evidence` |
| Any required scenario failed | `not_recommended` |
| All required scenarios passed; optional scenario failed | `conditional` |
| All required scenarios passed | `recommended` |

A recommendation never changes `human_decision`. The human decision remains `pending` until an authorized operator explicitly approves or rejects the session.

## Validation boundaries

Phase 20.17 does not:

- execute provider jobs merely to fill validation records;
- bypass governed attempt limits;
- modify Generated Media state or selection;
- modify ProductionTask completion;
- automatically enable/disable a provider;
- change LTX 2.3 workflows;
- treat Wan-specific implementation details as core VSCS concepts.

## Automated validation scope

Focused tests cover:

- the five-scenario Wan 2.2 validation pack;
- incomplete-evidence recommendation behaviour;
- successful recommendation with human decision remaining pending;
- failed required scenario behaviour;
- provider provenance enforcement for Generated Media evidence;
- prevention of premature human decision;
- durable JSON repository round-trip and provider filtering.

## Acceptance classification

- **Automated:** focused unit tests plus full regression suite.
- **Static:** Ruff and mypy.
- **UI-Functional:** manually create a session, populate scenario criteria/evidence, observe recommendation, then approve/reject.
- **Full Regression:** full project pytest suite.

## Roadmap correction

Phase 20.17 is defined as **Wan 2.2 Provider Capability Validation**, not a generic multi-provider implementation phase. Future provider expansion must consume this provider-neutral validation mechanism rather than introduce provider-specific authority into core domains.
