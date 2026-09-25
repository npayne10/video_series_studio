# VSCS Version 1.0 Test Plan

## Purpose

This plan defines the mandatory verification activities required before VSCS Version 1.0 can be approved.

## Test objectives

- Prove that each module behaves as specified.
- Prove that integrated workflows complete successfully.
- Detect regressions in previously approved milestones.
- Verify acceptable performance and resilience.
- Confirm that users can complete real production workflows through UAT.

## Test levels

### 1. Unit testing

Scope:

- Parsers
- Models
- Validators
- Builders
- Resolvers
- Packaging functions
- CLI command handlers
- Plugin contracts
- Utility functions

Pass criteria:

- All mandatory unit tests pass.
- No critical path is covered only by a skipped test.
- New defects include regression tests where practical.

### 2. Integration testing

Mandatory flows:

- Scanner → Migrator
- Migrator → Validator
- Validator → Builder
- Builder → Packaging
- Dependency Engine → Build ordering
- Repository → Prompt Compiler
- Prompt Compiler → Production Package
- Plugin interface → Provider implementation

Pass criteria:

- All required integration tests pass.
- Data passed between components remains valid.
- Failure states produce actionable diagnostics.

### 3. Regression testing

Scope:

- Previously approved fixtures
- Historical repository layouts
- Known defect reproductions
- CLI output contracts
- Report schemas

Pass criteria:

- Zero unexpected regressions.

### 4. Performance testing

Repository profiles:

| Profile | Asset count |
|---|---:|
| Small | 100 |
| Medium | 500 |
| Large | 1,000 |
| Very large | 5,000 |

Measure:

- Scan duration
- Validation duration
- Dependency resolution duration
- Package generation duration
- Peak memory use
- Output size

Thresholds must be agreed and recorded before RC1. Results must be repeatable on the nominated reference workstation.

### 5. Stress and resilience testing

Scenarios:

- Corrupted JSON, YAML, Markdown, and Python files
- Missing required directories
- Missing manifests
- Duplicate asset IDs
- Circular dependency chains
- Broken cross-asset references
- Interrupted writes
- Read-only directories
- Extremely large prompt files
- Invalid Unicode and encoding errors
- Plugin failure or timeout

Pass criteria:

- No unhandled process crash.
- No silent data loss.
- Repository content is not corrupted.
- Diagnostics identify the failing asset and cause.

### 6. Security and dependency checks

Scope:

- Dependency vulnerability scanning
- Unsafe archive extraction
- Path traversal protection
- Untrusted manifest handling
- Plugin loading boundaries
- Secret and credential handling

Pass criteria:

- No unresolved critical vulnerability.
- No known path traversal or arbitrary overwrite defect.
- Secrets are not written to reports or logs.

## Test environments

Minimum environments:

- Windows PowerShell development workstation
- Clean Python virtual environment
- Clean repository checkout
- Representative small and large CAR repositories
- Xorix reference repository

Additional environments may be added before RC1.

## Standard local test sequence

The exact commands may evolve with the repository, but each milestone should provide PowerShell commands equivalent to:

```powershell
git checkout main
git pull origin main
python -m pip install -e .
pytest -q
```

Focused milestone tests should run before the complete suite.

## Phase 20.18.2.3.6 focused acceptance

Automated Introduction Boundary Synthesis & Span Orchestration must verify:

- provider-neutral strategy selection remains deterministic;
- synthesis requests checksum-pin exact extracted source boundaries and introduced canonical references;
- Qwen introduction synthesis requires the governed source frame and canonical introduced asset reference;
- automated structural Introduction Keyframes do not claim final human semantic acceptance;
- the initial span can be materialized before a later Introduction Keyframe exists;
- orchestration renders the preceding span before synthesizing the next boundary;
- exact source-boundary extraction is automatic;
- dynamic span packages continue to use governed LTX frame normalization;
- assembled Shot frame count remains exact;
- ordinary monolithic Start Production remains disabled;
- manual Phase 3.5 controls remain available as explicit recovery paths;
- ProductionTask retry authority is not reset or multiplied by internal spans;
- the desktop remains responsive while provider orchestration runs;
- final visual QC remains an explicit human gate.

Local focused regression:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"

python -m pytest `
  tests/unit/test_phase_20_18_2_3_1_timed_asset_presence.py `
  tests/unit/test_phase_20_18_2_3_2_governed_internal_render_spans.py `
  tests/unit/test_phase_20_18_2_3_3_timed_canonical_reference_activation.py `
  tests/unit/test_phase_20_18_2_3_4_governed_introduction_keyframes.py `
  tests/unit/test_phase_20_18_2_3_5_ui_qc_functional_acceptance.py `
  tests/unit/test_phase_20_18_2_3_5_timed_asset_presence_workspace.py `
  tests/unit/test_phase_20_18_2_3_6_automated_introduction_span_orchestration.py `
  -q

Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

Live SHT-002 UAT must demonstrate:

```text
KEYFRAME_REQUIRED
    -> Run Automated Span Orchestration
    -> SPAN-001 generated
    -> frame 95 extracted automatically
    -> frame 96 synthesized automatically with CAP-CHR-005
    -> SPAN-002 generated
    -> final 144-frame Shot assembled
    -> QC_REQUIRED
    -> human visual QC
    -> ACCEPTED
```

No file-selection dialog is permitted in the normal automated path.

## Test data

Required fixtures:

- Known-good repository
- Repository with one defect per diagnostic type
- Duplicate-asset repository
- Circular-dependency repository
- Large generated repository
- Xorix reference production repository

Test data must be deterministic and must not contain private credentials or licensed production assets that cannot be stored in the repository.

## Defect handling

Every failed test must be assigned one of these outcomes:

- Product defect
- Test defect
- Environment defect
- Expected limitation

Product defects must include severity, reproduction steps, expected behaviour, actual behaviour, and the milestone that introduced or exposed the problem.

## UAT test set

Mandatory UAT scenarios:

1. Create a new repository.
2. Create representative assets for every supported category.
3. Validate a known-good repository.
4. Detect deliberately introduced defects.
5. Resolve dependencies and create deterministic build order.
6. Build and verify release packages.
7. Generate a complete episode production package.
8. Complete the Xorix end-to-end reference workflow.

## UAT evidence

For every UAT case, record:

- Test ID
- Tester
- Date
- Environment
- Input data
- Steps performed
- Expected result
- Actual result
- Pass or fail
- Defect references
- Evidence location
- Approval signature or recorded approval

## Final pass criteria

VSCS v1.0 testing is successful only when:

- Mandatory unit tests pass.
- Mandatory integration tests pass.
- Regression suite passes.
- Performance thresholds are met or formally waived.
- Resilience tests pass.
- Security review passes.
- All mandatory UAT cases pass.
- No critical defects remain.
