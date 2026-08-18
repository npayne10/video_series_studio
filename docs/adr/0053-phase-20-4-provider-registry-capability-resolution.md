# ADR 0053 — Phase 20.4 Provider Registry & Capability Resolution

## Status
Accepted for implementation; local validation pending.

## Context

Phase 19 established provider-neutral ProductionResource scheduling and runtime worker authority. Phase 20.3 established a provider execution contract that can bind only to a RUNNING ProductionQueue attempt with an active execution lease.

Phase 20.4 must connect scheduled production resources to durable execution-provider configuration without leaking provider details into ProductionTask or ProductionResource authority and without starting live provider execution.

## Decision

VSCS will maintain a durable ProviderRegistration registry separate from ProductionResource and separate from runtime adapter instances.

A ProviderRegistration owns:

- stable provider identity;
- adapter type;
- one bound ProductionResource identity;
- provider-neutral ProductionCapability declarations;
- supported ProductionTaskType declarations;
- supported GeneratedMediaKind declarations;
- optional endpoint;
- optional secret reference;
- enabled/disabled administrative state;
- last-known health state;
- non-secret provider configuration;
- non-secret metadata.

ProductionResource remains provider-neutral and is not modified with provider or endpoint fields.

## Credential boundary

Provider registrations may persist a `secret_reference`, but ordinary provider configuration must not persist obvious credential-bearing keys such as passwords, API keys, bearer tokens, authorization values, or secrets.

Phase 20.4 does not implement a secret store. It records only a reference suitable for later infrastructure composition.

## Capability resolution

ProviderCapabilityResolver evaluates one ProductionTask, one scheduled ProductionResource, and one ProviderRegistration.

A provider is eligible only when:

1. the provider is bound to the scheduled resource;
2. the resource is AVAILABLE;
3. the provider is ENABLED;
4. provider health is not explicitly UNHEALTHY;
5. the provider supports the ProductionTask type;
6. the resource satisfies every required ProductionCapability; and
7. the provider satisfies every required ProductionCapability.

Resolution is deterministic and diagnostic. It does not select a provider silently when multiple providers are eligible.

Provider health UNKNOWN is allowed in Phase 20.4 because this phase does not perform live network probes. Explicit UNHEALTHY state blocks eligibility. Live health checks belong to the provider-adapter implementation and monitoring phases.

## Persistence

Provider registrations are persisted as schema-versioned, project-local JSON documents using filesystem-safe provider identities and atomic replacement writes.

The registry supports deterministic lookup by provider ID and resource ID and survives process restart.

## Relationship to Phase 20.3

The authority chain is:

```text
ProductionTask
  -> ProductionResource scheduling
  -> ProviderRegistration capability resolution
  -> Phase 19 worker/lease/attempt authority
  -> ProviderExecutionContext
  -> ProviderExecutionAdapter
```

ProviderRegistration does not claim queue work, start attempts, create leases, submit jobs, or create GeneratedMedia.

## Relationship to Generated Media

Supported provider media kinds use the existing GeneratedMediaKind enum so provider declarations remain aligned with the authoritative media domain.

Provider output is still not GeneratedMedia. Output ingestion remains Phase 20.9.

## Backward compatibility

Existing RenderAdapterRegistry, legacy ProductionExecutor, ProductionResourceCatalog, and session worker behavior remain unchanged.

No existing provider-specific metadata is migrated automatically in Phase 20.4.

## Deferred

The following remain outside Phase 20.4:

- live provider connection and health probing;
- ComfyUI submission;
- runtime adapter construction from registrations;
- provider selection/routing policy;
- queue-to-provider execution;
- durable provider execution jobs;
- secrets storage;
- Generated Media ingestion;
- provider configuration UI.

## Consequences

VSCS now has a durable provider identity/configuration layer that can be resolved against scheduled production resources without making providers part of production authority. This provides the stable configuration seam required by Phase 20.5 live ComfyUI execution and Phase 20.6 queue-to-provider integration.
