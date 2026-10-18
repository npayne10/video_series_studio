# Phase 20.18.2.3.7.4 — Governed Timeline Revision Management

## Checkpoint 1 — Immutable successor service

Use the existing `AssemblyTimelineRevision.predecessor_revision` and
`JsonAssemblyTimelineRepository.create` append-only contract. A successor
retains the same Assembly ID and verified Episode Scope, is a new Draft
revision, and records the exact predecessor revision ID.

New Shots must be part of the current authoritative Episode plan and carry
approved media evidence. Existing Shot selections are carried forward
unchanged except for their sequence indexes when inserting a Shot. Replacing
existing media requires explicit operator justification. Silent drops,
unapproved media, stale predecessor fingerprint, duplicate Shot identity,
and changed authoritative scope all block the operation.

Before writing a successor the service re-reads the predecessor, validates
Shot ordering and planning readiness, verifies source media approval and
file integrity through the existing validator, and calls the existing
exclusive-create repository. It never mutates the predecessor.

**Current limitation:** the replacement justification is passed to the
publication service but is not yet persisted as a distinct audit artifact.
Before providing an operator-visible replacement UI, introduce an
append-only replacement decision record, bind it to predecessor and
successor fingerprints and require it for changed Shot selections.

## Next checkpoints

- Checkpoint 2: persisted replacement decision evidence, validated on replay
- Checkpoint 3: governed operator revision editor and read-only comparison
- Checkpoint 4: isolated project UI acceptance and baseline regression

Do not test successor publication on original TSR2. Preserve
`ASM-EP-001 / REV-001`, the published planning snapshot, all approved
SHT-001/SHT-002 media, and pending-QC SHT-003.

Acceptance commands:
```powershell
python -m ruff check . --fix
python -m ruff format .
git diff
python -m mypy src
python -m pytest -q tests/test_phase_20_18_2_3_7_4_timeline_successor.py -v
python -m pytest -q
```
