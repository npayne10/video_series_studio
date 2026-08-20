# ADR 0065 — Phase 20.15.1 Production Package Compilation & ComfyUI Input Assurance

## Status

Accepted for Phase 20.15.1 implementation; local validation and user acceptance remain pending.

## Context

Phase 20.15 proved that an approved scheduled `ProductionTask` can be started through the
existing Phase 19 queue, worker and lease authority and executed by the live ComfyUI provider.
The operator still had to browse for an already-created `production_package.json`.

That left a missing production boundary. VSCS already owns reviewed, provider-neutral production
authority in `production/production_packages.json`, including Assets, Camera, Lighting,
Environment, Action & Performance, Continuity, Style, Dialogue, Effects, canonical references
and the compiled Universal Production Description. `ProductionTask` authority is fingerprinted
from that Universal Production Description.

The committed ComfyUI workflow already consumes a semantic
`XorixProductionPackageLoaderV714` node, but VSCS did not compile the approved production
authority into the JSON consumed by that loader, nor did it prove that the loader outputs were
connected to the expected generation controls.

## Decision

Phase 20.15.1 adds a governed compilation boundary between approved Production Planning authority
and provider execution.

The execution path becomes:

Approved current Production Package
→ approved READY ProductionTask authority fingerprint
→ deterministic Production Package compilation
→ authority-bound persisted `production_package.json`
→ static ComfyUI input assurance
→ existing Phase 19 queue/worker/lease authority
→ existing Phase 20 provider execution
→ Generated Media ingestion.

### Authority

Compilation is permitted only when:

- the task is `VIDEO_GENERATION` and `READY`;
- the task authority is approved;
- the canonical package Shot matches the task Shot;
- Universal Production Description compilation is complete;
- cross-authority consistency passed; and
- the SHA-256 fingerprint of the canonical package Universal Production Description exactly
  matches the ProductionTask authority fingerprint.

No AI or provider may repair, replace or silently complete missing governed authority during
package compilation.

### Provider neutrality

The application compiler produces a provider-neutral executable production contract.

Translation into the `XorixProductionPackageLoaderV714` JSON contract is infrastructure work.
ComfyUI class names, loader output positions and workflow node semantics do not enter
ProductionTask or canonical Production Package authority.

### Persistence and stale protection

Compiled execution packages are stored under:

`production/compiled/<profile>/<production-task-id>/production_package.json`

Each artifact contains a VSCS manifest recording the task, authority revision and fingerprint,
source canonical package identity/fingerprint and a fingerprint of the executable package
content.

Execution rejects a package whose task identity, authority fingerprint or content fingerprint
does not match the current scheduled ProductionTask. A changed approved authority therefore
makes an older compiled package stale rather than silently executable.

### ComfyUI input assurance

Before compilation through the desktop execution backend, VSCS statically inspects the committed
production workflow and requires exactly one semantic `XorixProductionPackageLoaderV714`.

The assurance contract verifies loader outputs used for:

- target description;
- positive Shot prompt;
- negative prompt;
- previous approved final frame;
- output filename prefix;
- width and height;
- frame count;
- FPS;
- CFG;
- IC-LoRA strength; and
- canonical composition plan.

The check uses semantic node class/type relationships. Production code does not bind to numeric
ComfyUI node ID `107`.

Static assurance proves VSCS workflow wiring. Local UI/live validation remains required to prove
that the installed ComfyUI custom node version parses the generated JSON contract exactly as
expected.

### UI

The Production Execution workspace no longer requires the operator to browse for the normal
production package.

For the selected scheduled task it exposes:

- execution profile;
- package compilation state;
- Compile Production Package; and
- Start Production only when the compiled artifact is current and valid.

The existing application API may still accept an explicit package path for compatibility, but the
live backend validates that artifact against current ProductionTask authority before execution.

## Consequences

### Positive

- Approved planning information now has a deterministic path into provider execution.
- Camera, lighting, action/performance, environment, continuity, style and canonical references
  remain traceable through the compiled artifact.
- Stale package execution is blocked by authority fingerprint.
- The Production Execution UI no longer relies on manual task IDs or normal manual JSON browsing.
- ComfyUI workflow wiring becomes testable without an expensive render.

### Deliberately unchanged

Phase 20.15.1 does not implement:

- restart lease reconstruction or provider takeover (Phase 20.16);
- multi-provider routing/fallback (Phase 20.17);
- automatic Generated Media review, approval or selection;
- direct ProductionTask completion from provider success;
- post-production/transcoding;
- distributed locking; or
- a second queue, retry or concurrency authority.

Provider completion remains distinct from ProductionTask completion.
