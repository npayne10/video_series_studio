# VSCS — Operator Help and User Manual Index

**Version:** v0.2 (living documentation, updated 2026-11-10)  
**Source:** Current VSCS development branch; do not treat work-in-progress instructions as accepted production authority.

## Open first

1. [VSCS User Manual](VSCS_User_Manual.md) — project creation, Story, analysis, approved Story workflow, proposal/authority separation, CAP review, safety and acceptance steps.
2. [Automation Progress Audit](Automation_Progress_Audit.md) — which Story Automation buttons lack running feedback, safety constraints, remediation and Qt acceptance criteria.
3. [Production workflow architecture](../engineering/VSCS_Video_Production_Workflow_V2.md) — architecture/aspirational workflow for context; verify every action against the user manual and actual UI.
4. [B.5.22 disk-backed acceptance](../engineering/Phase_20_19_3B5_22_Disk_Backed_CAP_Persistence_Acceptance.md) — automated SQLite durability, governance and separate desktop operator acceptance.

## Known verified current path for B.5.22

`B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` → `STORY-001` Approved → Story Analysis complete → **Planning Proposals generated** (1 Episode + 1 Scene, no authority yet) → **Review Proposals…** → review/accept → **Compile Accepted…** → inspect actual **Production Planning** Episode/Scene records.

Next: Shot Proposals, review/accept/compile, register and bind assets, CAP context/queue/review, reviewed Draft CAP save, project close/reopen and provenance/status check. Each stage is a separate acceptance checkpoint. Do not modify `B5_19A_ACCEPTANCE`.

## B.5.26F F5 operator procedures — updated 2026-11-10

Read [VSCS User Manual — B.5.26F, F5.0–F5.3](VSCS_User_Manual.md#b526f--qwen-image-editing-f5-hardware-tests-and-gpu-memory-release-operator-procedure) for the **mandatory numbered procedure** when creating a fresh disposable Candidate lineage, running dual-workflow inspection, checking F5 hardware readiness, releasing ComfyUI GPU cache and conducting the first controlled source-conditioned Qwen edit.

**Operator-verified:** F5.1 and F5.2 code validated with **2,681 passed, 1 Windows symlink skip**; release button sent one accepted local `/free` request while idle; refreshed F5 readiness showed **14,174 MiB free of 16,311 MiB**, with Qwen nodes/model choices available. **Still pending:** genuine local Qwen GPU inference, new Candidate registration and visual quality acceptance.

The old `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` Engineering Control Room source **Candidate 2 is at attempt 2/2**, so do not use it for initial F5.3 hardware qualification. The manual now describes how to establish an **independent disposable project, genuine approved Draft CAP, source Candidate and saved failed semantic report** without fabricating evidence. Screens not yet walked end to end are marked as checkpoints. The paid semantic review requires separate cost approval.

**Mandatory documentation contract:** Every future recommendation implying action by the operator must provide a numbered, UI-accurate, reproducible step-by-step procedure, explicit preconditions, isolation, expected responses, evidence, stop/retry rules and separate acceptance gates. Update this index and the User Manual in the **same development phase and GitHub branch as the feature**. Do not present a mock-test pass or read-only preflight as real GPU acceptance.


## Required documentation for each UI action

| Item | Requirement |
|---|---|
| UI location | Navigation path, actual control label and screenshot |
| Preconditions | Project, Story/Shot/asset states and provider configuration |
| Effect | Read-only/proposal/Draft/Canon/governed/paid authority level |
| Result | Actual data path/record and expected status |
| Failure | Error text, underlying cause and safe recovery |
| Verification | Automated test ID and actual operator screenshot |
| Progress | Whether operation shows Running, provider, elapsed time, success/failure |
| Source status | UI verified / code confirmed / planned / not yet evidenced |

When a feature changes, modify the User Manual in the **same GitHub branch** as the code, then update applicable help UI and screenshots after local operator acceptance.

## Manual completion tracker

- [x] Project lifecycle basics — UI verified
- [x] Story source, metadata, analysis, approval — UI verified
- [x] Planning Proposal generation and proposal-vs-authority distinction — UI verified
- [x] Story Automation actions inventory — code confirmed
- [x] CAP batch read-only discovery and caching — prior operator UI verified
- [x] Disk-backed Draft CAP durability — automated integration verified
- [x] Proposal review/accept/compile — UI verified for one Episode and one Scene, no blockers
- [ ] Shot proposal review → governed Shot plan — awaiting current operator UI walkthrough
- [ ] Actual desktop Draft CAP save/reopen — awaiting current operator UI walkthrough
- [ ] Asset and reference canonical approval
- [ ] Provider selection, internal/hybrid/external generation
- [ ] Production Task / H3 readiness / scheduling
- [ ] Generated media, Episode Assembly and Post-production
- [ ] Project preferences, export, backup/restore, diagnostics
- [ ] Complete Automation progress indicator implementation — shared Planning/Shot runner committed, local acceptance pending; other actions outstanding
- [x] F5.1 dual-workflow and F5.2 ComfyUI memory-release operator guidance — documented and UI observed
- [ ] F5.3 clean disposable Qwen GPU inference and Candidate quality — awaiting actual local test
- [ ] Context-sensitive Help integration in VSCS

**No part of this index lifts the H3 live-execution hold or authorises paid provider work without explicit operator action.**

## Latest operator checkpoint — 2026-11-04

The `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` Episode and Scene both show Ready and 0:35 runtime, with 0:00 Scene budget remaining. Navigation relabelled in GitHub (Story → Episode Planner, top-level Production Packages) and approved by operator, awaiting local quality gates. Shared progress runner for Planning/Shot proposal generation committed, awaiting targeted and full regression. **Do not rerun Planning Proposals to test progress; it could overwrite accepted proposal records.** Run Shot Proposals once only after local validation, then inspect resulting proposal IDs/durations before human acceptance.

**Automation UX scope update:** shared progress is now committed for six Story proposal-generation actions; SQLite-linked Resolve Assets and synchronous Review Gaps are not migrated. Local acceptance is pending.
