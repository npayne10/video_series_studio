# Phase 17.4.1.3 — Prompt Graph Validation

## Purpose

This phase introduces the production-readiness quality gate between Prompt Graph construction and renderer-neutral prompt compilation.

The validator does not generate prompt text and does not contact ComfyUI. It evaluates whether the graph contains the production knowledge required for safe downstream compilation.

## Validation layers

### Graph integrity

The validator reports directed cycles as structured errors rather than allowing topological compilation to fail later.

### Required production sections

The default policy requires:

- visual intent
- camera
- lighting
- renderer
- quality

Policies are declarative and may be replaced for specialised production workflows.

### Mandatory content

Every mandatory node must contain descriptive content, except the structural graph root.

### Canonical production entities

Characters, ships, vehicles, locations, environments and props must bind to canonical asset identities. Visual entities can also require approved reference images.

An optional `PromptGraphResourceInventory` verifies that declared canonical asset and reference IDs are actually available.

### Continuity

Graphs using approved visual references require a continuity node by default. This prevents reference-driven shots from reaching compilation without an explicit continuity state.

### Dialogue

Dialogue nodes must carry spoken content by default. Voice generation and lip-sync execution remain separate rendering contracts.

## Completeness score

Validation produces a weighted score and percentage based on:

- acyclic graph structure
- required production sections
- mandatory descriptive content
- canonical asset resolution
- approved reference resolution
- continuity coverage
- dialogue content

A graph is `production_ready` only when:

1. no error diagnostics exist; and
2. the completeness percentage meets the configured threshold, which defaults to 85 percent.

Warnings reduce completeness but do not automatically fail validation.

## Public contracts

- `PromptGraphValidator`
- `PromptGraphValidationPolicy`
- `PromptGraphResourceInventory`
- `PromptGraphValidationReport`
- `PromptGraphValidationIssue`
- `PromptGraphValidationSeverity`
- `PromptGraphCompleteness`

## Bootstrap

`PromptGraphValidator` is registered as a shared application service. Future ACPP, batch compilation and production workspace features must use this shared validator rather than constructing independent readiness rules.

## Deliberate exclusions

This phase does not:

- compile prompt sections or prompt text
- optimise renderer-specific wording
- create UI panels
- submit render jobs
- perform live CAP or reference discovery

Persistence-backed resource inventories and UI presentation will be added through later integration phases.

## Readiness for Phase 17.4.1.4

The Prompt Graph Compiler may consume a graph only after validation. Production compilation should require `production_ready`; preview tooling may display incomplete graphs together with their structured diagnostics.
