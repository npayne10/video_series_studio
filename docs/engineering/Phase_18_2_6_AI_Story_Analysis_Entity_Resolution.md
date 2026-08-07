# Phase 18.2.6 — AI Story Analysis & Entity Resolution

## Objective

Add provider-neutral AI enrichment to the deterministic Story Analysis pipeline while preserving human control over canon.

## Architecture

Pipeline order:

1. `story.analysis.engine` — deterministic baseline and provenance.
2. `story.analysis.ai_entity_resolution` — AI enrichment and production-entity proposals.
3. `story.knowledge_graph` — deterministic SKG projection.

The AI stage never overwrites the baseline `AnalysisResult` and never creates or modifies XPD/CAP assets automatically.

## Entity recognition

The AI contract supports characters, ships, planets, locations, vehicles, props, technology, organisations, species, environments, and other production-relevant entities. Each proposal includes a type, description, aliases, explicit attributes, source evidence, and confidence.

## Entity resolution

AI proposals are matched against existing project assets using category compatibility and normalized names/aliases. Resolution states are:

- `new`
- `existing`
- `possible_duplicate`
- `uncertain`

Existing matches retain the XPD asset ID and asset name.

## Review state

Every candidate starts as `proposed`. The review UI can change session state to `approved` or `rejected`. These decisions are intentionally not persistent in this phase. Phase 18.2.7 will persist approved Story Intelligence and canonical mappings.

## Narrative metadata

The AI provider may also extract narrative summary, themes, tone, setting, and production notes. These are metadata outputs rather than canonical production entities and therefore do not require individual entity approval.

## Providers

- `TemplateStoryAIAnalysisProvider` provides deterministic offline/test behaviour.
- `OpenAIStoryAIAnalysisProvider` uses structured OpenAI output when OpenAI is configured.
- Provider failure or unavailable credentials fall back to the template provider during Story Workspace composition.

## UI

The Story Workspace adds **Review AI Entities**. The review table exposes proposal status, entity type, name, confidence, resolution state, XPD match, and description. Approve/reject/reset operates on immutable review-session candidates.

## Deferred

- persistence of approval decisions
- creation/update of XPD assets
- CAP synchronization or generation
- automatic canonical promotion
- cross-story entity memory
- duplicate merge operations
- AI-driven SKG mutation

These remain explicit later-phase responsibilities.
