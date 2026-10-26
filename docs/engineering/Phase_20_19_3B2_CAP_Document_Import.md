# Phase 20.19.3B.2 — CAP Document Import, Category Mapping & Source Provenance

Date: 2026-10-26
Status: Initial backend review-first importer committed; local tests pending
Safety: No H3 video generation, ComfyUI image generation, source asset mutation, CAP creation or automatic approval.

## Delivered
- `application/caps/document_import.py` exports `preview_cap_docx(path)`, `CAPDocumentProposal`, `CAPDocumentImportService` and `CAPDocumentImportError`.
- DOCX is read via the Python standard library as an archive and the Word main-document XML. Read-only preview discovers successive `CAP-XXX-000 v1.0` headings in **multi-CAP** documents, assigns supported type by prefix, extracts identifiable document sections, and SHA256-hashes original document bytes.
- Supported prefix-to-native-category mapping: CHR Character, LOC Location, SHP Ship, VEH Vehicle, PRP Prop, ENV Environment, UNI Uniform, LGT Lighting. Unrecognized types are not imported.
- Extracted sections: Visual Design Intent, Character/Architectural Identity, Variables, Master Creation Prompt, Dependencies, Continuity. Preserve these sections as **evidence for review**; no automatic, unreviewed assumption about fixed attributes or allowed values.
- Explicit human mapping in `to_draft_specification` supplies canonical attribute fields and controlled variable choices. The resulting specification is a non-authoritative Draft using the existing `CAPStructuredSpecification` and `CAPStructuredSpecificationService`.
- `CAPDocumentImportService.apply_reviewed` fails on existing structured CAP draft, wrong project asset category, non-Draft CAP, source/project ID mismatch, incomplete category-specific identity and invalid source document. Does not create a missing asset/CAP or auto-promote to approved.
- Source SHA256, source ID, category and source description become part of persisted specification provenance. Document's printed LOCKED status is *not* treated as VSCS approval.
- ZIP/XML read is bounded by whole-document and main XML size limits; avoids extraction of embedded files, external URL resolution and media copying. Parsing only Word main-document prose has known limits (tables/text boxes/inline relationships may require later inspection).
- Focused tests cover multi-CAP sections and digest, collision refusal, human review gate, wrong mapping, duplicate draft and invalid DOCX.

## User source examples
1. **Character**: the Xorix Character CAP contains persistent facial/physical identity, design intent, master prompt, changing pose/expression/wardrobe, dependencies and continuity.
2. **Location**: the Xorix Location CAP encodes architectural layout/materials, window position, room geometry, future view/state variants, dependencies and continuity.
3. **Critical project-scope collision:** Xorix source `CAP-LOC-001` names James Spence's Apartment; the separate synthetic Golden Path project uses `CAP-LOC-001` for Engineering control room. `apply_reviewed` additionally requires the selected target asset to be an existing project Asset with an existing Draft CAP, preventing silent overwrite. An explicit ID remapping/revision workflow is deferred, not silently approximated.

## Known limitations and upcoming increments
- **No UI wizard yet.** Operators cannot preview and apply proposals through the native Assets/Canonical Profiles UI. That integration needs design and UI tests.
- **No automatic DOCX interpretation of category identity values.** Human supplies `canonical_attributes` and `allowed_variants`; section extraction is suggestive only. Later AI-assisted field mapping must be reviewed and strongly validated.
- **No bulk multi-CAP transaction.** Only one reviewed proposal at a time.
- **No faithful import of document images, tables, footnotes or change-tracked content.** DOCX textual paragraphs only.
- **No archived original document stored in project yet**; original SHA256 is persisted, and original source must remain accessible until archive/backup policy is implemented.
- Existing draft is protected from overwrites. Category selection is derived from source CAP prefix; verifying source's explicit Category text is a future enhancement.
- Read/compare/write is not atomic under concurrent editors. Transactional compare-and-swap needs an explicit service contract before multiple UI windows can import simultaneously.
- Existing tests use in-memory service mocks for reviewed handoff; the earlier 20.19.3B.1 tests already exercise the real SQLite CAP repository. End-to-end importer→SQLite integration remains a further acceptance task.

## Acceptance commands
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b2_cap_document_import.py -v
python -m pytest -q tests/test_phase_20_19_3b_structured_cap_specification.py tests/test_phase_20_19_3b1_cap_database_persistence.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Expected: all pass. No new runtime UI control in this increment; smoke-check Assets and Canonical Profiles unchanged in disposable `Episode Audit` project, four bindings remain Draft, H3 hold present. If local Ruff/mypy flags anything, fix in GitHub directly and re-pull.
