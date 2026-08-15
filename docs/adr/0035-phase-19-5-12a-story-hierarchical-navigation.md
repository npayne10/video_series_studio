# ADR-0035 — Phase 19.5.12A Story Workspace Hierarchical Navigation

## Decision

The Story Workspace automation and planning actions move from the increasingly crowded horizontal Story toolbar into a hierarchical navigation tree beneath the main `Story` section.

The visible structure is:

- Story
  - Workspace
  - Story Definition
  - Automation
    - Story Analysis
    - Planning Proposals
    - Shot Proposals
    - Canonical Asset Resolution
    - Performance
    - Environment
    - Camera & Lighting
    - Continuity
    - AI Review & Gap Detection
  - Proposal Review
  - Production Planning

The Story toolbar retains direct Story lifecycle controls such as create/import/edit/duplicate and governance actions.

## Compatibility

This is a UI-only refactor. The established flat `QListWidget` remains alive as an internal navigation controller so existing section indexes, View-menu actions and historical tests continue to operate. The dock displays a `QTreeWidget` that delegates top-level selections to that controller.

Story child actions invoke the already-existing Story Workspace buttons. No automation service, proposal contract, authority transition, approval rule, canonical resolution rule or production compiler is duplicated or changed.

## Rationale

Phase 19.5 added enough Story automation actions that a flat horizontal toolbar no longer scales. Adding multiple toolbar rows would postpone rather than solve the problem, and adding a second permanent vertical menu inside Story would duplicate the application's navigation model. Hierarchical navigation provides room for future capabilities while preserving a single primary navigation system.

## Governance

Navigation changes MUST NOT:

- regenerate proposals;
- accept or reject proposals;
- mark governed authority Ready;
- change canonical identity;
- alter Production Approval;
- submit provider or render jobs.

The refactor only changes where established user actions are surfaced.
