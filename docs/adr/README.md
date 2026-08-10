# VSCS Architecture Decision Records

Architecture Decision Records (ADRs) capture significant VSCS design decisions, the context that led to them, and their consequences. ADRs are part of the engineering contract and are maintained alongside the implementation that depends on them.

## Status values

- **Proposed** — under review; not yet authoritative.
- **Accepted** — current architectural decision.
- **Superseded** — replaced by a later ADR; retained for history.
- **Deprecated** — still visible for compatibility but should not be used for new work.

## Format

Each ADR records:

1. Status
2. Context
3. Decision
4. Consequences
5. Alternatives considered
6. Future notes

## Current records

- [ADR-0000 — VSCS Architecture Principles](ADR-0000-VSCS-Architecture-Principles.md)
- **ADR-0001 through ADR-0008** — reserved for retrospective Phase 18 decisions when formalized.
- **ADR-0009** — reserved for Production Package & Prompt Compilation.
- [ADR-0010 — Structured Production Knowledge Authority and Persistence](ADR-0010-Structured-Production-Knowledge.md)
- [ADR-0011 — Behaviour Profile Domain Model](ADR-0011-Behaviour-Profile-Domain-Model.md)
- [ADR-0012 — Behaviour Profile Persistence and Repository](ADR-0012-Behaviour-Profile-Persistence-and-Repository.md)
- [ADR-0013 — Behaviour Profile Services and Governance](ADR-0013-Behaviour-Profile-Services-and-Governance.md)
- [ADR-0014 — Behaviour Profile Editor](ADR-0014-Behaviour-Profile-Editor.md)
- [ADR-0015 — CAP ↔ Behaviour Profile Integration](ADR-0015-CAP-Behaviour-Profile-Integration.md)
- [ADR-0016 — Episode Planner](ADR-0016-Episode-Planner.md)
- [ADR-0017 — Scene Planner](ADR-0017-Scene-Planner.md)
- [ADR-0018 — Authoritative Production Planning Workspace](ADR-0018-Authoritative-Production-Planning-Workspace.md)
- [ADR-0019 — Governed Shot Planning Boundary](ADR-0019-Governed-Shot-Planning-Boundary.md)
- [ADR-0020 — Governed Shot Asset Resolution](ADR-0020-Governed-Shot-Asset-Resolution.md)

ADRs are immutable in intent once Accepted. Clarifications may be added, but a material architectural change should create a new ADR that explicitly supersedes the earlier decision.
