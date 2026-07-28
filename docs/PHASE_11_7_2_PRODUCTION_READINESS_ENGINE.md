# Phase 11.7.2 — Combined Production Readiness Evaluation (PRE) v1.0

PRE combines the latest CIEE technical report and SIEE semantic report for a canonical image into one production-readiness decision.

## Scoring

- Technical quality: 30%
- Semantic quality: 50%
- Canon consistency: 20%

The canon score is read from the SIEE `Canon consistency` metric. Blocking CIEE or SIEE metrics always force `REGENERATE`.

## Decisions

- `PASS`: score 80 or higher, low canon risk, no blockers
- `REVIEW`: score 55–79 or medium/high canon risk
- `REGENERATE`: score below 55, critical canon risk, or blocking failures

## Canon risk

PRE classifies canon risk as Low, Medium, High, or Critical using the canon-consistency score and the number of semantic violations.

## UI workflow

1. Select a canonical image.
2. Run `Evaluate Selected Image…` to create the CIEE report.
3. Run `Semantic Evaluate Selected…` to create the SIEE report.
4. Run `Production Readiness…`.

PRE saves both a current report and a timestamped history report under:

`Canonical Assets/<ASSET-ID>/.metadata/evaluation/`

Files:

- `<image>.pre.json`
- `<image>.<timestamp>.pre.json`

The report records technical, semantic, canon, and overall scores; decision; canon risk; readiness state; blockers; recommendations; and links to the source evaluation reports.
