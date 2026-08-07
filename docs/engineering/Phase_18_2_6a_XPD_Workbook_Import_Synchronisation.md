# Phase 18.2.6a — XPD Workbook Import / Synchronisation Foundation

## Purpose

Bridge the established Xorix Production Database workbook into the VSCS-native Asset database so AI Story Analysis resolves production entities against the existing canonical registry.

## Approved source schema

The importer targets worksheet `XAR_Master` and validates the approved XPD v1.1 22-column header:

Asset ID, Asset Name, Category, Subcategory, Asset Owner, Parent Asset, Production Priority, First Season, First Episode, First Clip, CAP Status, CAP Version, SVB Status, ARC Status, MSR Status, PRL, Variant Count, Dependencies, Image Filename, Prompt Filename, Last Modified, Notes.

The supplied reference workbook contains 155 asset rows across Character, Uniform, Ship, Location, Prop, Planet, Environment, Lighting, Technology, Vehicle, Effect, Audio and Camera categories.

## Architecture

`XPDWorkbookReader` reads `.xlsx` OOXML directly without adding a spreadsheet runtime dependency. `XPDWorkbookImportService` compares normalized workbook rows with the active project's `AssetService`. `XPDProvenanceStore` retains the complete original source row in `.vscs/xpd_import_provenance.json`.

The synchronization direction in this phase is intentionally one-way:

`XPD Workbook -> Preview -> Confirm -> VSCS Asset database`

VSCS does not write changes back to the workbook.

## Dry-run classifications

- `new` — Asset ID and canonical name do not exist in VSCS.
- `update` — matching Asset ID/name/category exists, but projected XPD metadata differs.
- `unchanged` — canonical asset and/or previous row hash already match.
- `conflict` — Asset ID collides with a different canonical identity, or the canonical name exists under another ID.
- `invalid` — required identity is missing or the XPD category is unsupported.

Conflict and invalid rows are never auto-imported.

## Canonical field projection

The generic Asset database receives Asset ID, canonical name, mapped category, notes as description, CAP-derived readiness status, and selected searchable XPD metadata tags. The complete 22-column source row remains available in provenance so no workbook metadata is discarded.

CAP `Locked`/`Approved` maps to Asset `approved`; review states map to Asset `review`; other states map to Asset `draft`.

## AI Entity Resolution integration

No special alternate resolver is introduced. Phase 18.2.6 already resolves against `AssetService`. Therefore, after the XPD import, AI candidates such as `Iron Horizon` and `Xorix` resolve against imported canonical assets automatically.

## User interface

The Assets workspace provides `Import / Synchronise XPD`. The dialog supports workbook selection, validation/dry-run preview, classification summary, detailed row review, explicit import confirmation and completion reporting.

## Deliberate boundaries

This phase does not implement workbook write-back, automatic conflict merging, CAP creation, entity approval persistence, background file watching, or cross-project XPD synchronization. Those capabilities belong to later phases.
