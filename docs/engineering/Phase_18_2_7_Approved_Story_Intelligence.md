# Phase 18.2.7 — Persistence / Approved Story Intelligence

## Purpose

Persist human-reviewed AI Story Analysis decisions so entity approvals, rejections, canonical XPD links, and automatically extracted narrative metadata survive application restarts and repeated analysis runs.

## Architecture

The transient Story Analysis pipeline remains unchanged. `EntityResolutionResult` is still regenerated from the current story source. `ApprovedStoryIntelligenceService` overlays persistent human decisions after each run.

Persistent state is project-local:

`.vscs/story_intelligence/<story-id>.json`

The persisted document contains the story/source revision, AI narrative metadata, and one `StoryEntityDecision` for each candidate that has been reviewed or reset.

## Canonical entity behavior

- Existing XPD match + Approve: persist the canonical Asset ID link.
- Possible duplicate + Approve: explicitly accepts the proposed XPD match and persists that link.
- New entity + Approve: after UI confirmation, create one canonical VSCS Asset with a generated `CAP-<category>-NNN` ID.
- Newly promoted assets are created with `Draft` production status. Human approval confirms entity identity; it does not imply CAP or production readiness.
- Reject: persist rejection without modifying or deleting canonical XPD assets.
- Reset to Proposed: persist the reset decision; any canonical asset already created is retained rather than destructively removed.

## Automatically persisted metadata

AI narrative metadata does not require per-field approval. Summary, themes, tone, setting, production notes and metadata confidence are saved whenever the AI Entity Review is refreshed successfully.

## Safety and consistency

- Raw manuscript text remains unchanged.
- Raw deterministic analysis and the SKG remain derived artifacts, not persistence sources.
- Existing XPD assets are never overwritten by Story Intelligence approval.
- New canonical identities are Draft assets and enter the normal XPD/CAP workflow.
- Candidate IDs are deterministic, allowing decisions to be restored across repeated AI analysis runs.
- The original `AIEntityReviewDialog(story, engine, parent)` call signature remains compatible; persistence is injected as a keyword-only service.

## UI

The existing **Story Analysis → Review AI Entities** workflow now persists actions immediately:

- Approve Candidate
- Reject Candidate
- Reset to Proposed
- Re-run AI Analysis

Reopening the dialog restores prior review states and XPD links. Approving a genuinely new candidate requires explicit confirmation before VSCS creates a Draft canonical asset.

## Out of scope

- Automatic CAP generation for newly approved assets
- Deleting canonical assets when a story decision is reset/rejected
- Cross-project Story Intelligence
- Automatic merging of possible duplicates
- Revision-diff conflict adjudication
