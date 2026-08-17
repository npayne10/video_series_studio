# ADR-0036 — Phase 19.6.1 ProductionTask Domain & Governance

## Decision

VSCS Architecture vNext introduces `ProductionTask` as the provider-neutral unit of executable production work.

A ProductionTask describes **what production work must be performed**, not which provider, workflow, model, endpoint, renderer node or transport mechanism will execute it. Provider selection and workflow compilation remain downstream concerns for later Phase 19.6/20 work.

Phase 19.6.1 deliberately introduces ProductionTask alongside the existing `ProductionNode`. The ProductionNode-to-ProductionTask migration is deferred to Production Pipeline modernisation and ProductionGraph integration so this phase does not destabilise the existing execution foundation.

## Authority

For Phase 19.6.1, a ProductionTask may originate only from an explicitly approved Universal Production Description (UPD).

Each task carries immutable source-authority provenance:

- authority type;
- authority identity;
- authority revision;
- authority fingerprint;
- approval state;
- human approver identity.

Task derivation does not modify Story, Canonical, Planning, Production Package or UPD authority.

## Provider-neutrality

ProductionTask contains provider-neutral capability requirements such as `VIDEO_GENERATION` or `VOICE_GENERATION`.

ProductionTask must not contain provider/execution detail such as:

- provider identity;
- renderer identity;
- workflow identity;
- model identity;
- provider endpoint;
- renderer node identity.

Governance validation rejects provider-specific execution metadata leaked through generic metadata/provenance fields.

## Lifecycle boundary

Phase 19.6.1 derivation creates tasks only in `PLANNED` state.

Later state transitions belong to subsequent architecture layers:

- readiness and blocking: ProductionGraph / Scheduler;
- running/completed/failed: ProductionQueue / executor;
- supersession: provenance/invalidation governance.

This prevents task creation from silently scheduling or executing production work.

## Invariants

- ProductionTask is immutable.
- A task cannot depend on itself.
- Task dependencies, inputs, outputs and capabilities cannot contain duplicates.
- At least one provider-neutral capability is required.
- At least one expected output contract is required.
- Approved authority must identify the human approver.
- ProductionTask is not a replacement production authority; it is a deterministic derivative of governed authority.

## Migration

No legacy production subsystem is removed in Phase 19.6.1.

Later phases will:

1. compile approved UPDs into ProductionTasks;
2. modernise historical Production Pipeline stages;
3. migrate ProductionGraph nodes toward ProductionTask identity;
4. generalise RenderQueue execution toward ProductionQueue;
5. add resource-aware scheduling without introducing provider detail into ProductionTask.
