# ADR-0034 — Proposal Review, Acceptance & Auto-Compilation Orchestration

## Status
Accepted for Phase 19.5.10 implementation.

## Decision
Phase 19.5.10 turns the shared Phase 19.5 proposal review surface into the explicit human governance point for proposal review and acceptance. AI never accepts a proposal and acceptance is never equivalent to final Production Approval.

A proposal must be human-reviewed before it can become Accepted. Bulk review/acceptance is an explicit human action and leaves unresolved or ambiguous canonical assets, rejected proposals and continuity conflicts unaccepted.

Human acceptance authorizes deterministic orchestration through existing public governed planner services. Accepted Episode, Scene and Shot proposals may be created and promoted to Ready as a mechanical consequence of that human authorization because downstream governed planners require Ready parent authority. The orchestrator never bypasses those planner services and never overwrites an existing governed authority whose content differs from the accepted proposal.

Automation proposal Scene IDs use the proposal-space form `EP-001-SC-001`, while governed Scene Planning uses canonical `EP-001-SCN-001`. The orchestration manifest records the mapping between proposal identity and governed authority identity rather than rewriting either subsystem. Shot identity is mapped through the same Scene identity translation.

Phase 19.5.5 canonical entity proposals are Story-scoped and do not establish per-Shot asset usage. Therefore Phase 19.5.10 does not invent Shot asset bindings from Story-level entity proposals. Accepted Action/Performance, Environment, Camera, Lighting and Continuity proposals remain deferred until the existing governed Shot-to-Asset and specialist-planner prerequisites are satisfied. This is a deliberate safety boundary, not a bypass target.

The orchestrator writes a project-local `automation/automation_compilation.json` report containing Story revision, human operator identity, proposal-to-authority mappings, created/reused authority counts, deferred proposals and blockers.

Phase 19.5.10 never performs final Production Review, final Production Approval, provider submission or render execution.
