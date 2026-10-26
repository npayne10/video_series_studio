# Phase 20.19.3B.1 — Database-backed CAP persistence and architecture audit incorporation

**Date:** 26 October 2026
**Scope:** Read-only verification contract plus pytest-only, temporary project SQLite database.
**H3 hold:** Active; no video or image submission authorized.

## 1. Incorporated historical architecture baseline

The operator-supplied file **`VSCS_Architecture_Workflow_Audit_2026-10-24.md`** (reviewed 24 October 2026, repository `npayne10/video_series_studio`, branch `phase-20.18.2.3.6.3-local-r2v-provider-evaluation`) is retained as an architecture reference, not a claim that every historical observation is still current. This integration preserves its ten decision areas and maps them to today's verified or pending stages. It does not overwrite another locally untracked document.

### A. Executive findings and target
The active approved baseline is `docs/engineering/VSCS_Video_Production_Workflow_V2.md`: Story → canon → Production → hierarchy → governed planning → provider-neutral packages → video → audio/voices → QC → assembly → master/export/archive. The success condition is a **playable finished episode with reviewed audio, continuity and provenance**, not merely 2,000+ unit tests or a provider preflight.

Core priorities: automation with human approval; free/local-first provider choice; continuity of identity across shots; physically plausible images; traceability and ease of use.

### B. Runtime UI and navigation
The historical static base `MainWindow` listed File/View/Tools/Help, twelve sidebar destinations, and duplicated View destinations; several base-class placeholder observations were explicitly **static** and subject to dynamically installed widget overrides. Phase 20.19.2 subsequently collected a real runtime inventory with dynamic Story and Production Planning workspaces. Preserve the approved menu rationalization direction from Phase 20.19.4: contextual Production navigation, Library (Assets/CAP/References), Tools/diagnostics, meaningful Help, and non-destructive aliases. No menu deletes in this phase.

### C. 23-step production workflow retained
1. Project setup and defaults; 2. Create/Import Story; 3. Story analysis; 4. Human canon review; 5. Production setup; 6. Episode/Scene/Shot structure; 7. Per-shot asset requirements; 8. Canonical asset registration; 9. CAP/reference/behavior/physical rules; 10. Scene plan; 11. Shot plan; 12. resource/readiness/schedule; 13. provider-neutral package; 14. prompt/reference provider compilation; 15. preview; 16. video rendering/ingestion; 17. voice/dialogue/lip-sync; 18. ambience/Foley/SFX/music; 19. shot QC; 20. timeline assembly; 21. grading/mix/captions/master QC; 22. export; 23. release/archive. Every step requires persisted provenance and explicit ownership.

The supplied audit's per-shot invariants remain binding: governed opening/closing boundary, one-time provider approval, frame/fps technical probing, audio/video distinct governance, protected approved predecessors and QC transitions.

### D. Historical capability report vs current evidence
The 24 October static audit identified Story and Planning as possible placeholders and had no witnessed end-to-end Story run. Subsequent operator screenshots and the current Golden Path **do** demonstrate Story `STORY-001` approved; accepted AI semantic/Episode/Scene/Shot proposals; governed Episode `EP-001`, Scene `EP-001-SCN-001`, Shot `EP-001-SCN-001-SHT-001` Ready; four inferred Draft binding records for Location/Environment/Ship/Prop. This does **not** show CAP/reference readiness, an approved ProductionTask, real H3 render, complete episode sound or mastering. Keep all remaining gates open.

### E. Approved roadmap
Historical proposed G0–G10 remains an outcomes framework: G0 baseline, G1 UI shell, G2 Story-to-Shot, G3 video, G4 continuity, G5 dialogue, G6 audio/lip-sync/music, G7 QC, G8 timeline/post, G9 delivery, G10 full UAT. The actual phase numbering is now 20.19.1 H3 hold, 20.19.2 runtime inventory, 20.19.3 Golden Path and asset readiness, 20.19.4 navigation/Help rationalization, and later governed video/audio/master work. Do not reopen or renumber completed work without evidence.

### F. Priority release blockers retained
No witnessed playable full episode; H3 live video still held; no accepted continuous cross-shot scene; voice/lip-sync/SFX/music and mastering remain unverified. UI duplicate routes and local resource/cost policy need later consolidation. Approved media identity, provenance and backup/recovery remain essential.

### G. Non-destructive rule
Do not delete runtime-installed workspaces or replace asset/CAP services, do not alter `D:\VSCS TSR2`, do not touch pending SHT-003 QC, and do not treat a test fixture as H3 submit permission. The locally untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` must be preserved. This document incorporates its decision content and updates factual status; it is **not a byte-for-byte replacement** of that file.

## 2. SQLite persistence reality

The project-scoped `DatabaseManager` currently uses SQLite/SQLAlchemy with a schema-versioned manager. `canonical_asset_profiles` already contains `production_metadata_json`. Phase 20.19.3B uses metadata key `vscs.structured_cap_specification.v1`, preserving other existing metadata and CAP identity.

Phase 20.19.3B.1 adds `tests/test_phase_20_19_3b1_cap_database_persistence.py` with temporary SQLite, real `CAPRepository` and `CAPService`. Cases:
- Rehydrate Draft Location specification and legacy metadata from SQLite.
- Store distinct Character/Location specifications without mixing identities.
- Reject specification updates after CAP becomes Approved.
- Reject category mismatches without writing records.
- Read a legacy CAP without a specification envelope.

**No SQLite schema migration is required at this stage**. These tests do not validate concurrent editor writes, and DOCX-to-CAP parsing/section evidence mapping remains a separate forthcoming increment.

## 3. CAP category acceptance

Character: facial, anatomical, identity, wardrobe invariant and permitted poses/expressions.
Location: layout, geometry, dimensions, materials, spatial anchors, doors/windows and allowed time/occupancy/weather/camera changes.
Ship/vehicle, prop/technology, environment/planet and uniform: domain-specific identity keys.
Category validator must reject a canonical attribute being freely variable. Source `LOCKED` is documentary state only; CAP approval remains an explicit application lifecycle decision.

**Import collision:** Xorix `CAP-LOC-001` is James's Apartment; the synthetic Golden Path `CAP-LOC-001` is Engineering Control Room. Match by active project namespace, not bare ID.

## 4. Local acceptance

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b_structured_cap_specification.py tests/test_phase_20_19_3b1_cap_database_persistence.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Expected no database mutation outside pytest's temporary fixtures. UI: open `Episode Audit`, confirm four Draft bindings; no Master/CAP/Asset status changes. H3 hold must remain active. Record outputs before declaring acceptance.
