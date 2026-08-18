# ADR 0057 — Phase 20.8 Live Monitoring & Recovery

## Status

Accepted for implementation; local validation pending.

## Context

Phase 20.6 established real queue-authorised provider execution and Phase 20.7 made provider execution identity and observations durable. A durable execution record can survive process reconstruction, but the transient provider handle cannot. VSCS therefore needs a provider-neutral way to reconstruct queryable provider state, monitor active executions, classify stale/unreachable work, and reconcile provider observations to Phase 19 authority when that authority is still available.

Phase 19 deliberately keeps workers, leases, and ProductionQueue runtime state session-scoped. Phase 20.8 must not fabricate those authorities after restart.

## Decision

### 1. Durable execution identity is the monitoring anchor

`DurableExecutionJob` remains the restart-safe source for provider job identity, request/workflow identity, provider metadata, task/queue/resource/worker linkage, and the last observed provider state.

Monitoring does not create a new execution identity or retry counter.

### 2. Provider adapters may restore transient handles

A `ProviderExecutionHandleRestorer` capability reconstructs a transient `ProviderExecutionHandle` from a durable execution record. The existing rendering bridge implements this capability by rebuilding a `RenderJob` from persisted `provider_job_id`, `render_job_id`, `request_id`, submitted time, progress, and state.

Native Python provider objects remain non-persistent.

### 3. Detached monitoring never fabricates Phase 19 authority

`LiveExecutionMonitoringService.inspect()` may reconstruct a provider handle, query the provider, and persist the observed provider state. If a detached provider reports terminal state, the result is `RECONCILIATION_REQUIRED`.

It does not claim a queue entry, recreate an execution lease, complete a queue entry, or create a retry.

### 4. Live-session recovery may reconcile through the existing queue service

`recover_live()` may reconcile a provider observation only when the original Phase 19 lease is still active and exactly matches the durable execution record. Reconciliation delegates to the existing `QueueProviderExecutionService`, preserving Phase 19 heartbeat, completion, failure, cancellation, and retry authority.

If the original lease is unavailable, the provider observation remains durable but queue reconciliation is deferred.

### 5. Provider communication failures are not execution failures

A provider query exception results in `PROVIDER_UNREACHABLE`. VSCS does not silently mark the provider execution or ProductionQueue attempt failed merely because monitoring could not contact the provider.

A recently observed job recommends `RETRY_PROVIDER_QUERY`; a job already beyond the stale threshold recommends `REQUIRE_OPERATOR_REVIEW`.

### 6. Staleness is an observation-health signal

`ExecutionMonitoringPolicy.stale_after_seconds` compares the monitoring time to the durable job's previous `updated_at`. A stale job that can still be queried successfully is reported as `STALE_ACTIVE` and refreshed durably. It is not failed or retried automatically.

### 7. Terminal durable records are not re-polled

Once the durable provider state is completed, failed, or cancelled, Phase 20.8 returns the persisted terminal state without making another provider query. Queue reconciliation, if still required, remains a separate authority decision.

## Consequences

- Active provider work can be re-queried from durable identity after service reconstruction.
- Live executions continue to renew Phase 19 leases through the existing queue integration.
- Provider outages cannot silently create duplicate retries while external work may still be running.
- Detached terminal observations are visible and durable but do not mutate session-scoped queue authority.
- Full restart reconstruction of queues/workers/leases remains Phase 20.16.

## Deferred

Phase 20.8 does not implement:

- durable ProductionQueue, worker, resource, or lease reconstruction;
- automatic process-start recovery orchestration;
- Generated Media ingestion;
- technical output validation;
- execution UI;
- provider load balancing or failover submission;
- automatic resubmission of ambiguous/unreachable provider jobs.
