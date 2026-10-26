# Phase 20.19.3B.3 — Guided CAP DOCX Import, Mapping & Human Review UI

Date: 2026-10-26
Status: Initial integrated UI implementation committed; local Windows tests and UAT pending

## Implemented
- Existing **Canonical Profiles** workspace now exposes **Import CAP DOCX…** while an active project is open.
- `CAPDocumentImportDialog` allows a DOCX selection, previews each recognized CAP in a multi-asset document, shows category, source SHA256, original text sections and warnings.
- Target list is existing **Draft CAPs only**. The dialog preselects the source ID only when matching; it does **not** automatically map Xorix IDs to a different project's assets.
- Operator manually enters `key=value` locked canonical attributes and optional variant choices `key=view1|view2`; whitespace, empties and duplicate keys are rejected.
- On Save, backend category/schema/identity checks precede an **explicit Yes/No** dialog stating source checksum, target, Draft status and no approvals.
- On Yes, call the existing `CAPDocumentImportService.apply_reviewed`, which refuses duplicate structured specs, wrong category, mismatched source/target IDs or non-Draft CAPs. Saves metadata only through CAP service; no reference or image creation, no auto-approval.
- Unit/UI tests added for mapping validation, only Draft targets, preview read-only behavior and Cancel no mutation.
- Existing CAP creation, CAP generation, reference lifecycle and production controls remain unchanged.

## Operator acceptance
1. In the **disposable Episode Audit** project, open Canonical Profiles. **Import CAP DOCX…** should be present. Do not apply the Xorix documents to this project.
2. Select a valid DOCX sample. Detected CAPs, source SHA256, extracted sections and missing-section warnings should appear. Changing selection should clear stale manual mappings.
3. Verify only pre-existing Draft CAPs appear as targets. A Source ID not matching the available target should not be silently remapped.
4. Type intentionally invalid mapping (`layout=` or duplicate key), Save: validation warning, no database changes.
5. Press Cancel: no status change, no new CAP, no references, no provider action.
6. For a future specially created disposable matching Draft CAP and matching test DOCX, Save should require explicit confirmation; answer No and verify no mutation. A separate authorized Yes exercise may store only Draft metadata, but never auto-approve.
7. Reopen Episode Audit Shot Asset Resolver: four bindings remain Draft, no asset promoted to Ready.
8. H3 live-video hold remains active.

## Known limitations / next work
- This is manual, explicit mapping **not** automatic extraction of structured attribute names or values.
- There is no document archival or exact page/paragraph provenance mapping, only source SHA256 and extracted sections.
- Full operator-friendly per-category form controls and cross-project remapping UX are still pending.
- Existing backend importer parses Word main-document paragraphs only; tables/text-box layout could need additional fidelity work.
- No original DOCX copied to project; source bytes must be retained by operator.
- No automatic creation of missing CAPs; operator registers and drafts CAP through the existing workspace first.
- Concurrent editing and transactional compare-and-swap are not yet implemented.
- A test-only read/write importer→SQLite integration should precede bulk acceptance.
- The UI is not yet equivalent to a production-ready bulk CAP ingestion studio.

## Quality gates
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b3_cap_import_ui.py tests/test_phase_20_19_3b2_cap_document_import.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
Tests are not claimed to pass until locally executed. Apply Ruff fixes directly to GitHub, then repull.
