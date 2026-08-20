# ADR 0068 — Phase 20.16.1 Governed Retry Override

## Status

Accepted for implementation in Phase 20.16.1.

## Context

ProductionTask execution has a provider-neutral attempt policy whose default maximum is three attempts. Phase 20.16 preserves every durable provider attempt across restart and correctly blocks direct execution after the configured maximum is exhausted.

A production operator can nevertheless encounter recoverable external failures, for example ComfyUI completing without a usable production output. Deleting durable attempts, resetting attempt counters, or silently increasing the retry limit would destroy production provenance and weaken human governance.

## Decision

VSCS introduces a durable `GovernedRetryAuthorization` that grants exactly one additional attempt beyond the currently effective maximum.

An authorization:

- is created only by an explicit operator action;
- requires a non-blank human identity and reason;
- is bound to the ProductionTask production ID, task ID, and current authority fingerprint;
- records the exact additional attempt number being authorized;
- is persisted under the project `.vscs/provider_executions` authority area;
- never changes, deletes, renumbers, or overwrites prior durable attempts;
- becomes consumed naturally when the authorized attempt is created;
- cannot be stacked while an unused authorization already exists.

The effective execution limit is:

`configured maximum attempts + valid governed retry authorizations for the current authority fingerprint`.

If the authorized attempt also fails, another explicit human authorization is required before the next attempt.

## Eligibility

A retry override is eligible only when:

1. the configured/effective attempt limit is exhausted;
2. all existing provider attempts are terminal;
3. no authoritative Generated Media exists for the ProductionTask;
4. there is no already-unused retry authorization.

An active provider execution, successful governed media, or an unused authorization blocks creation of another override.

## Authority changes

Retry authorizations are bound to the ProductionTask authority fingerprint. If production authority changes, old unused retry authorizations do not authorize execution under the new authority.

## UI

Production Execution exposes:

- retry override state and attempt counts;
- `Authorize Additional Retry` only when eligible;
- mandatory `Authorized by` and `Reason` prompts;
- the normal `Start Production` command only after the override makes one additional attempt available.

The next attempt retains normal sequential numbering (for example A001–A003 failed, authorization grants A004).

## Consequences

- Production history remains immutable and auditable.
- Retry limits remain meaningful defaults rather than permanent dead ends.
- Human operators retain explicit authority for exceptional additional executions.
- Providers and AI systems cannot silently grant themselves more attempts.
- The feature does not alter Generated Media approval, selection, ProductionTask completion, or provider recovery authority.
