# Phase 17.4.0.3.2 — Manifest Loader and Discovery

## Status

Build and integration implementation.

## Objective

Allow VSCS to discover, parse, validate and register workflow manifests without
allowing one malformed document to prevent application startup.

## Discovery root

Workflow manifests are discovered recursively from:

```text
<config_root>/workflows/manifests
```

The root is derived from the existing VSCS environment configuration. A missing
directory is treated as an empty workflow catalogue.

## Loader behaviour

`WorkflowManifestLoader` provides:

- Parsing of one UTF-8 JSON manifest
- Immutable `WorkflowManifest` reconstruction
- Supported manifest-version checks
- Recursive `*.json` discovery
- Registration into `WorkflowRegistry`
- Stable JSON writing for generated or edited manifests

## Diagnostics

Discovery returns a `ManifestDiscoveryResult` containing:

- Number of JSON files discovered
- Successfully loaded workflow IDs
- Structured diagnostics
- Loaded and error counts

Diagnostic levels are:

- Info
- Warning
- Error

Malformed JSON, invalid manifest models, unsupported versions, file-system
errors and duplicate workflow IDs are reported without terminating discovery.
Valid manifests in the same directory continue loading.

## Duplicate policy

The default discovery policy preserves the first successfully registered
workflow manifest and reports later duplicates as warnings. Callers may request
explicit replacement when implementing future workflow-management tools.

## Bootstrap integration

Bootstrap now registers:

- `WorkflowRegistry`
- `WorkflowManifestLoader`
- `ManifestDiscoveryResult`

Discovery runs during dependency-graph construction. No workflow JSON is
executed and no renderer is contacted.

## Deferred work

This phase does not include:

- Render-request compatibility validation
- Installed model or custom-node inspection
- Workflow JSON node validation
- ComfyUI payload compilation
- User-facing workflow management

Those responsibilities belong to Phases 17.4.0.3.3 and 17.4.0.4.

## Completion outcome

VSCS can now discover all valid installed workflow manifests, preserve startup
when some documents are malformed, and expose a complete structured discovery
report for future diagnostics and UI presentation.
