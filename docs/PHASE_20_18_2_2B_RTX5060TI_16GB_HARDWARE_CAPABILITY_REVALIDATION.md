# Phase 20.18.2.2b — RTX 5060 Ti 16GB Hardware Capability Revalidation

## Purpose

Phase 20.18.2 originally validated the LTX 2.3 one-Shot provider path on an
NVIDIA GeForce RTX 4060 8 GB GPU at a governed maximum of 7 seconds / 168
frames at 24 fps. The production machine now uses an NVIDIA GeForce RTX 5060
Ti 16 GB. The larger GPU must not inherit a longer production limit by
assumption alone.

This phase introduces a controlled revalidation envelope for the exact
RTX 5060 Ti 16 GB + LTX 2.3 provider pair while retaining the previously
validated 7-second production ceiling until live evidence justifies promotion.

## Policy

The hardware resolver now distinguishes three cases:

1. RTX 4060 / 8 GB-class hardware remains validated at 7 seconds.
2. An RTX 5060 Ti with at least 14.5 GiB reported VRAM is marked
   `revalidation-required`.
3. Other higher-VRAM GPUs remain `conservative-until-validated` at 7 seconds.

For the RTX 5060 Ti 16 GB only, the preview execution profile may compile
controlled revalidation candidates at:

- 8 seconds — 192 governed frames / 193 provider frames
- 10 seconds — 240 governed frames / 241 provider frames
- 12 seconds — 288 governed frames / 289 provider frames
- 14 seconds — 336 governed frames / 337 provider frames
- 16 seconds — 384 governed frames / 385 provider frames

Production and master profiles remain capped at the production-approved
7-second / 168-frame limit. Preview durations above 7 seconds that are not one
of the staged candidates are rejected. Durations above 16 seconds are rejected.

Compiled provider payloads record both the production-approved ceiling and the
active revalidation ceiling. A package above 7 seconds is explicitly marked:

- `revalidation_active: true`
- `production_approved: false`

This prevents a revalidation experiment from being mistaken for normal
production authority.

## Live acceptance sequence

Do not lengthen SHT-001 or SHT-002 merely because the GPU has changed. Complete
the existing 6-second baseline first so provider execution, reference handling,
media ingestion and continuity can be compared against the established path.

After the 6-second baseline succeeds:

1. Confirm ComfyUI `/system_stats` reports NVIDIA GeForce RTX 5060 Ti and
   approximately 16 GB total VRAM.
2. Use the preview execution profile for revalidation shots.
3. Run 8 seconds first.
4. Require two consecutive successful provider completions with valid media and
   no out-of-memory failure before advancing.
5. Repeat at 10, 12, 14 and 16 seconds in order.
6. Stop at the first candidate that cannot complete repeatably.
7. The highest candidate with two consecutive successful runs is eligible to
   become the new production maximum.
8. Promotion of that measured maximum requires a follow-up authority change;
   this phase intentionally does not self-promote based only on VRAM size.

## Automated acceptance

The implementation must prove that:

- the exact RTX 5060 Ti 16 GB is detected as `revalidation-required`;
- its production ceiling remains 7 seconds until live acceptance;
- unrelated 16 GB GPUs do not inherit the RTX 5060 Ti envelope;
- production execution rejects an 8-second Shot before promotion;
- preview execution accepts only the staged 8/10/12/14/16-second candidates;
- provider frame counts preserve the LTX `(frames - 1) % 8 == 0` requirement;
- preview rejects non-staged durations above 7 seconds;
- preview rejects durations above 16 seconds;
- hardware policy provenance clearly marks revalidation packages as not
  production-approved.

## Promotion gate

Phase 20.18.2.2b is implemented when the controlled envelope and its tests pass.
It is fully *validated* only after live RTX 5060 Ti runs establish a repeatable
maximum. Until then the normal production ceiling remains 7 seconds.
