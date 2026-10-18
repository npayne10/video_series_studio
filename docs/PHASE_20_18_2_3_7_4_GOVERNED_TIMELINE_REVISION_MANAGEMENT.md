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

## Checkpoint 2 — Persisted Replacement Decision Evidence

An immutable replacement-decision JSON file is created at
`.vscs/episode_assembly/replacement_decisions/<decision_id>.json`, using
exclusive-link publication with no overwrites. It stores the operator identity,
justification, exact previous and replacement selections, predecessor and
successor revision IDs, both revision fingerprints, Shot ID, schema version and
a SHA-256 fingerprint of the complete decision payload.

`JsonReplacementDecisionRepository.get` rejects malformed files, unknown
fields, wrong identities and fingerprint mismatches. Before publishing changed
predecessor selections, `publish_successor_revision` requires the exact
set of persisted decisions and verifies each decision against the re-read
predecessor and candidate. Unrelated or absent decisions fail closed.
Additions do not require replacement decisions. The existing media validator
still must pass before immutable timeline publication.

The decision is **operator-supplied evidence**, not an automatic media
approval. Do not create a decision without an actual human operator review,
and do not treat it as authority to bypass human Shot QC. A persisted
decision can exist without a subsequently published successor if final
media or planning validation blocks publication; it is never silently
rewritten.

The operator-facing replacement editor and deliberate review confirmation
remain for Checkpoint 3. No production TSR2 revision should be created for
these backend tests.

Focused tests:
```powershell
python -m pytest -q tests/test_phase_20_18_2_3_7_4_replacement_decision_evidence.py -v
python -m pytest -q tests/test_phase_20_18_2_3_7_4_timeline_successor.py -v
```

## Checkpoint 3 — Governed Successor Draft Editor

Episode Assembly now includes **Governed Successor Draft Revision** below the
initial Draft publication controls. Select an Episode, discover and inspect an
existing persisted Draft, enter a **new** revision identity, then use the
existing coverage matrix to stage only additions/replacements. Save each
staged Shot's source range using verified approved-media auto-fill.

Click **Preview Successor Differences** to carry forward unchanged selections
and display a read-only table identifying carried, added and replaced Shots,
previous/proposed media and proposed frame ranges. Changes to staging, source
ranges, revision ID, operator or justification invalidate the preview.

For replacements the operator identity and justification are mandatory.
**Confirm & Publish Successor Draft** requires a successful preview and
a separate affirmative human confirmation. Replacement decisions are
published as immutable evidence and verified against exact predecessor and
successor fingerprints before the successor is appended. In the event of a
later media-validation failure, the already-written evidence remains an
audit record, not authority to publish.

No implicit Shot QC, Episode completion, Picture Lock or ProductionTask state
changes occur. The existing initial Draft flow remains separate.

### Acceptance

Run:
```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
git diff --check
python -m pytest -q tests/test_phase_20_18_2_3_7_4_successor_editor_ui.py -v
python -m pytest -q tests/test_phase_20_18_2_3_7_4_replacement_decision_evidence.py -v
python -m pytest -q tests/test_phase_20_18_2_3_7_4_timeline_successor.py -v
python -m pytest -q
```

Use only `D:\\VSCS TSR2 - TEST 4B5` or a fresh copy for UI acceptance.
**Never publish a successor in the original TSR2 project while testing.**
Test 1: with no predecessor inspected, Preview blocks, Publish is disabled.
Test 2: inspect REV-001, stage an approved new Shot (if present) and record
verified frames; Preview shows carried and added Shots.
Test 3: stage approved alternate media for an existing Shot (if available),
enter operator and justification; Preview shows its replacement. Verify a
missing operator or justification blocks.
Test 4: reject publication confirmation; no new revision or decisions created.
Test 5: only on an isolated project with actual eligible approved media,
confirm publication and inspect the new persisted successor.
Check unchanged original revision checksum, SHT-003 pending-QC gate, and
Episode completion disabled.
