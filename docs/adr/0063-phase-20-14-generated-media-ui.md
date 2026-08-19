# ADR 0063 — Phase 20.14 Generated Media UI

## Status

Accepted for Phase 20.14 implementation; local validation pending.

## Context

Phases 20.9 through 20.13 established authoritative Generated Media ingestion, technical validation, human review/approval, revision and supersession governance, authoritative selection, and ProductionTask completion reconciliation. Those authorities existed only as application services and persisted JSON records. Operators need one desktop workspace that can inspect those records and invoke governed media actions without bypassing the established application boundaries.

## Decision

### Application facade

The presentation layer uses `GeneratedMediaUiService`, a thin application facade that receives repository factories. The facade creates existing `GeneratedMediaPersistenceService`, `GeneratedMediaReviewService`, and `GeneratedMediaSelectionService` instances and exposes only operator-oriented queries and commands.

The presentation layer does not mutate `GeneratedMedia`, governance history, selection records, or JSON files directly.

### Project-scoped composition

`MainWindow` creates the Generated Media UI service only while a project is open. Repository roots are scoped to the active project:

- `.vscs/generated_media`
- `.vscs/generated_media_selections`

The workspace therefore follows the current project lifecycle and does not create detached global media authority.

### Browsing and discovery

The workspace is a browser, not an identifier lookup form. Operators are not required to know or type a `production_id` or `ProductionTask` identity.

The Generated Media repository contract exposes a deterministic `list_all()` query so the application facade can discover the productions represented by authoritative project media without hard-coding Xorix or another production. This query does not alter the Generated Media JSON schema.

The workspace loads all Generated Media for the active project and presents cascading filters:

- Production — `All Productions` plus discovered production identities;
- Episode — `All Episodes` plus episodes constrained by the selected production;
- Task — `All Tasks` plus readable task labels constrained by the selected production and episode.

Task labels favor production context such as media kind and shot/scene plus a short stable-ID suffix. The complete `ProductionTask` identity remains available as a tooltip and in the detail panel for auditing.

The main table exposes:

- production;
- episode;
- scene;
- shot;
- readable task context;
- media kind;
- governance state;
- revision;
- technical-validation status;
- authoritative selection status.

The detail view exposes:

- complete stable media, production, episode, scene, shot and ProductionTask IDs;
- managed project-relative file path;
- execution/provider/workflow provenance;
- immutable Generated Media governance history;
- immutable selection history;
- revision candidates for the same production intent.

Refresh re-reads authoritative project persistence, rebuilds the available filter choices, and preserves currently selected filters when those identities still exist.

### Human governed commands

The UI supports explicit commands already governed by Phases 20.11 and 20.12:

- submit for review;
- approve;
- reject;
- select;
- supersede and select.

Every command requires an explicit human actor ID, display name, and nonblank reason/comment. The UI delegates authority checks and lifecycle rules to the existing application services. It cannot directly construct an APPROVED, REJECTED, SELECTED, or SUPERSEDED state.

### Technical validation

Phase 20.14 displays persisted Phase 20.10 technical-validation evidence but does not run FFprobe or define technical requirements. Technical validation remains an application/infrastructure responsibility outside this workspace command set.

### ProductionTask completion

The workspace does not directly complete ProductionTasks. Phase 20.13 reconciliation remains the sole authority for converting governed selected media into ProductionTask completion.

### Provider execution

Live provider controls, queue execution controls, leases, retries, and provider monitoring remain outside the Generated Media workspace and are deferred to Phase 20.15 Production Execution UI.

## Consequences

- Generated Media authority becomes visible and operable from the main VSCS desktop shell.
- Operators can browse media immediately without knowing internal IDs.
- Production, episode and task filters are derived from authoritative project media and remain production-generic.
- Operators can trace media from provider provenance through technical status, review, selection, and supersession history.
- UI commands cannot bypass the existing human-governed application services.
- Project closure detaches the workspace from persistence automatically.
- The UI remains provider-neutral and production-generic.

## Deliberately deferred

Phase 20.14 does not implement:

- provider execution/queue controls;
- automatic or AI review/approval/selection;
- technical validation execution or profile editing;
- ProductionTask completion controls;
- distributed user identity/authentication integration;
- richer production/episode display names from a future production catalogue;
- media playback/transcoding infrastructure;
- delivery/mastering UI;
- multi-user locking or concurrent review resolution.
