# VSCS Version 1.0 Release Plan

## Purpose

This document defines how VSCS progresses from active development to Release Candidate and final Version 1.0 approval.

## Release model

VSCS uses milestone-based development with gated approval.

Each milestone must be:

1. Implemented in GitHub.
2. Pulled into the local repository.
3. Tested with the supplied PowerShell commands.
4. Approved by the project owner.
5. Recorded in the milestone tracker and changelog.

## Branch strategy

Preferred workflow:

- `main` remains the approved integration branch.
- Larger or risky changes use a dedicated feature branch.
- Small, isolated documentation or low-risk changes may be committed directly to `main` when explicitly approved.
- Release candidates use a versioned release branch or tag.

## Version strategy

- Development milestones increment pre-1.0 semantic versions.
- Release Candidate tags use `v1.0.0-rc.N`.
- Final release tag is `v1.0.0`.

## Release stages

### Development

- Features are implemented according to the roadmap.
- Automated tests are added with each feature.
- Defects are corrected before milestone approval.

### Feature complete

Entry criteria:

- All implementation phases through Phase 22 are complete.
- No planned Version 1.0 feature remains unimplemented.

### System test

Entry criteria:

- Feature complete baseline exists.
- Test fixtures and clean installation environment are ready.

Exit criteria:

- Mandatory unit, integration, regression, performance, and resilience tests pass.
- No critical defects remain.

### User Acceptance Testing

Entry criteria:

- System testing has passed.
- UAT scripts, test data, and expected outcomes are approved.

Exit criteria:

- Every mandatory UAT scenario passes.
- Results and evidence are recorded.
- Project owner signs off UAT.

### Release Candidate

RC1 entry criteria:

- System testing and UAT complete.
- Documentation complete.
- Dependency and security review complete.
- Release notes prepared.

RC1 exit criteria:

- Clean installation succeeds.
- Upgrade and rollback procedures are verified.
- Release artefacts are reproducible.
- No critical or unapproved high-severity defects remain.

### Production release

The final release requires:

- Tag `v1.0.0`.
- Final changelog entry.
- Approved release notes.
- Archived test and UAT evidence.
- Project-owner approval.

## Defect severity

### Critical

System unusable, data corruption, unsafe operation, or no viable workaround.

Release rule: zero open critical defects.

### High

Major feature unavailable or unreliable with significant operational impact.

Release rule: zero open high defects unless a written waiver is approved.

### Medium

Functional defect with a practical workaround.

Release rule: may be deferred only when documented and accepted.

### Low

Minor usability, documentation, or cosmetic issue.

Release rule: may be scheduled for a maintenance release.

## Release artefacts

Version 1.0 must include:

- Source release
- Installation instructions
- Configuration examples
- Versioned schemas
- CLI help
- User Guide
- Developer Guide
- API reference
- Test summary
- UAT sign-off
- Changelog
- Release notes

## Rollback

Before final release, verify that:

- The previous stable version can be restored.
- Repository and project data remain recoverable.
- Migrations document reversibility or backup requirements.
- Failed upgrades do not leave partial state without diagnostics.

## Post-release

After Version 1.0:

- Monitor defects and operational feedback.
- Use maintenance releases for corrections.
- Route new features to the Version 1.1 roadmap.
