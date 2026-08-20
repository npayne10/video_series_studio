# ADR 0066 — Phase 20.15.2 Live Production Monitoring Dashboard

## Status

Accepted for Phase 20.15.2 implementation; local automated, static, UI and live ComfyUI validation remain pending.

## Context

Phase 20.15.1 established a governed path from approved Production Planning authority through an authority-bound compiled production package into the live ComfyUI production workflow. During real production testing, the desktop workspace exposed only coarse text status and required manual execution refresh.

The existing live ComfyUI integration already reads `/queue`, `/history/<prompt_id>` and `/system_stats`. The Phase 20.5 live adapter intentionally maps active execution to coarse progress markers while no finer progress signal is available from its HTTP polling contract. ComfyUI system statistics include system and device data that were previously used mainly for provider health rather than operator monitoring.

Operators need a production-oriented dashboard that shows as much real execution information as VSCS can verify without fabricating provider telemetry.

## Decision

Phase 20.15.2 introduces a read-only, provider-neutral production telemetry contract and a graphical Live Production Monitor in the Production Execution workspace.

### Authority boundary

Telemetry is observational only. It does not:

- claim or renew a ProductionQueue entry independently;
- create a second lease or retry authority;
- mutate ProductionTask state directly;
- approve or select Generated Media;
- reconstruct live provider authority after restart; or
- replace Phase 20.16 recovery and provider reconciliation.

Automatic monitoring uses the existing `reconcile` execution path. That path remains responsible for provider observation, lease renewal, durable execution updates and output ingestion.

### Provider-neutral telemetry

The application contract can represent:

- execution state and overall progress;
- live versus durable-summary status;
- execution, provider and provider-job identities;
- scheduled resource and queue-entry identity;
- current production stage and optional current node;
- optional step current/total progress;
- elapsed and estimated remaining time;
- queue state, position and running/pending counts;
- provider health and endpoint;
- device identity and memory observations; and
- provider-neutral system metrics and operator messages.

Current-node and sampler-step fields are optional. VSCS must not invent these values when the provider does not expose them.

### ComfyUI telemetry

The initial live reader uses existing proven HTTP APIs:

- `/queue` for running/pending prompt state and queue position;
- `/system_stats` for provider health and device/VRAM information; and
- the existing reconciliation path, which already uses `/history/<prompt_id>` and `/queue` to update execution lifecycle and outputs.

No new WebSocket dependency is introduced in this subphase. The telemetry contract deliberately includes optional node/step fields so a future ComfyUI event-stream transport can populate them without redesigning the application or UI contract. Until then, the dashboard clearly states when detailed node/sampler progress is unavailable.

### Graphical dashboard

The Production Execution workspace adds a Live Production Monitor containing:

- overall progress bar;
- current production operation;
- queue state/position and running/pending counts;
- optional current-step progress bar;
- elapsed and estimated remaining time;
- provider and ComfyUI prompt identity;
- ComfyUI health; and
- first-device identity and VRAM use when reported.

The monitor automatically polls active current-session execution every two seconds. The existing manual Refresh Execution Status control remains available as a fallback.

### Restart boundary

If VSCS restarts, a durable execution record may still be displayed, but it is explicitly marked `DURABLE SUMMARY` and `live=False`. Automatic polling does not start from a durable record alone. Phase 20.15.2 does not fabricate a worker claim, lease or live provider handle from durable observations.

Full restart recovery remains Phase 20.16.

## Consequences

### Positive

- Long-running ComfyUI productions become visible without repeatedly pressing Refresh Execution Status.
- Existing execution reconciliation and lease authority remain the sole live execution path.
- Operators can see ComfyUI queue state, prompt identity, health and device/VRAM information.
- The dashboard can adopt finer provider progress later without redesigning the UI contract.
- Automatic reconciliation can discover completion and trigger the already-governed Generated Media ingestion path.

### Limitations

- Current ComfyUI HTTP polling does not expose reliable current-node or sampler-step progress to this integration.
- Overall progress remains as precise as the existing provider execution handle; current Phase 20.5 running progress may therefore remain coarse.
- Estimated remaining time is withheld for known coarse 10%/50% state markers rather than presenting a misleading ETA.

### Deliberately unchanged

Phase 20.15.2 does not implement:

- restart lease reconstruction or takeover;
- provider event-stream/WebSocket transport;
- multi-provider orchestration;
- provider cancellation through global `/interrupt`;
- automatic Generated Media approval or selection;
- direct ProductionTask completion from provider success; or
- post-production/transcoding.
