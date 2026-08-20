# ADR 0069 — Phase 20.16.2 Profile-Scoped Execution Attempts

## Status

Accepted for implementation in Phase 20.16.2.

## Context

Preview, Production, and Master are distinct production execution profiles with different operational purposes. A failed Preview render must not consume the limited attempts intended for Production or Master. Phase 20.16.1 introduced human-governed retry overrides after the configured attempt limit was exhausted, but that limit was still counted across the ProductionTask as a whole.

The Phase 19 ProductionQueue attempt number is also part of durable execution identity and restart recovery. Resetting that number to A001 for each profile would create duplicate queue-attempt identities for the same queue entry and weaken the established one-to-one relationship between `ProductionQueueAttempt` and `DurableExecutionJob`.

## Decision

VSCS keeps one immutable global queue-attempt sequence per ProductionTask while enforcing attempt budgets independently per execution profile.

The supported profiles are:

- `preview`
- `production`
- `master`

Each profile receives the ProductionTask's configured base attempt allowance independently. With the default policy this means three attempts for Preview, three for Production, and three for Master.

Example:

- global A001–A003 may be Production attempts 1–3;
- global A004 may be a human-authorized Production attempt 4;
- the first later Preview attempt may be global A005 but is Preview attempt 1/3.

The global identity remains authoritative for queue history and restart recovery. The profile-local count is authoritative for retry-policy eligibility.

## Durable profile identity

New executions receive a durable profile assignment keyed by execution ID under:

`.vscs/provider_executions/profiles/assignments.json`

Execution records created before Phase 20.16.2 did not persist enough information to determine their historical profile safely. Such legacy execution identities are treated as `production`. VSCS does not guess or rewrite old provider history.

Generated Media remains linked to the durable execution ID through provenance, so its profile is resolved through the same durable execution-profile assignment. Legacy Generated Media therefore also resolves to Production.

## Profile-scoped retry overrides

Governed retry authorizations remain immutable human authority records. Phase 20.16.2 adds durable profile scope for those authorizations under:

`.vscs/provider_executions/retry_overrides/profiles.json`

Legacy Phase 20.16.1 retry authorizations with no explicit profile assignment resolve to Production.

An override grants one additional attempt only to its assigned profile. A Preview override does not increase Production or Master allowance.

## Runtime queue authority

When executing a selected profile, VSCS reconstructs the complete global durable attempt history so queue attempt numbering remains contiguous. The session-scoped queue entry receives an effective maximum large enough to represent the remaining allowance for the selected profile.

The persisted ProductionTask attempt policy is not rewritten.

Only one execution for a ProductionTask may be non-terminal at a time, regardless of profile. This prevents concurrent profile executions from competing for the same task/queue authority.

## UI behavior

The existing Production Execution profile selector controls:

- compiled Production Package profile;
- attempt eligibility;
- retry override scope;
- start authority;
- durable execution status/telemetry where no live execution is attached.

The UI may display both the profile-local attempt count and the global execution ID. This distinction is intentional.

## Consequences

- Preview failures no longer consume Production/Master budgets.
- Production and Master retain independent retry authority.
- Durable queue attempt identities remain globally unique and restart-safe.
- Existing Phase 20.16/20.16.1 data remains readable without destructive migration.
- Human retry override authority remains explicit and profile-specific.
- Generated Media approval, selection, ProductionTask completion, provider selection, and schedule authority are unchanged.
