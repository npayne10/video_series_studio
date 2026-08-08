"""Phase 18.2.11.1 CAP architecture assessment and rationalisation baseline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CAPAssessmentDisposition(StrEnum):
    """Required architectural treatment for an existing CAP capability."""

    KEEP = "keep"
    REFINE = "refine"
    REPLACE = "replace"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class CAPCapabilityAssessment:
    """One audited CAP capability and its approved architectural treatment."""

    capability_id: str
    capability: str
    disposition: CAPAssessmentDisposition
    rationale: str
    target_contract: str


@dataclass(frozen=True, slots=True)
class CAPContractGap:
    """One production-contract capability missing from the current CAP architecture."""

    gap_id: str
    capability: str
    reason: str
    required_before_production_planning: bool = True


MASTER_REFERENCE_AUTHORING_POLICY = (
    "Master canonical references are authored externally in ChatGPT. VSCS registers, "
    "classifies, validates, approves, locks, versions and supplies those references to "
    "downstream production; it is not the authoritative master-reference authoring system."
)


CAP_CAPABILITY_ASSESSMENTS: tuple[CAPCapabilityAssessment, ...] = (
    CAPCapabilityAssessment(
        "cap.asset-link",
        "CAP linkage to a registered XPD/Asset identity",
        CAPAssessmentDisposition.KEEP,
        "A CAP must remain subordinate to one canonical production-asset identity.",
        "Production Planning consumes the asset ID and CAP together as one canonical contract.",
    ),
    CAPCapabilityAssessment(
        "cap.lifecycle-version",
        "CAP status and version lifecycle",
        CAPAssessmentDisposition.KEEP,
        "Version and approval state are required for controlled downstream consumption.",
        "Only explicitly production-eligible CAP states may satisfy generation readiness.",
    ),
    CAPCapabilityAssessment(
        "cap.canonical-description",
        "Free-form canonical description",
        CAPAssessmentDisposition.REFINE,
        "The field is useful but mixes identity and facts in prose.",
        "Retain readable prose while exposing structured canonical facts/invariants.",
    ),
    CAPCapabilityAssessment(
        "cap.visual-identity",
        "Visual identity",
        CAPAssessmentDisposition.REFINE,
        "Visual invariants are essential but need explicit completeness semantics.",
        "Represent stable visual identity separately from shot-specific appearance and readiness.",
    ),
    CAPCapabilityAssessment(
        "cap.production-notes",
        "Free-form production notes",
        CAPAssessmentDisposition.REPLACE,
        "The current field can contain scene-specific actions and mixes multiple responsibilities.",
        "Split into functional identity, canonical constraints and production guidance.",
    ),
    CAPCapabilityAssessment(
        "cap.legacy-reference-paths",
        "Legacy CAP reference_paths collection",
        CAPAssessmentDisposition.REMOVE,
        "It duplicates the structured CanonicalReference repository and has no role/status lifecycle.",
        "Structured CanonicalReference records become the only production reference source.",
    ),
    CAPCapabilityAssessment(
        "reference.structured-registry",
        "Structured canonical reference registry",
        CAPAssessmentDisposition.KEEP,
        "Typed/versioned references with approval and lock metadata are the correct foundation.",
        "All imported ChatGPT master references are registered as structured references.",
    ),
    CAPCapabilityAssessment(
        "reference.generic-role",
        "Primary / Secondary / Supplementary reference roles",
        CAPAssessmentDisposition.REPLACE,
        "Importance alone cannot tell production which viewpoint/reference to use for a shot.",
        "Use production roles/viewpoints such as primary, front, rear, port, starboard, top, detail and variant.",
    ),
    CAPCapabilityAssessment(
        "reference.lifecycle",
        "Imported / Candidate / Approved / Archived reference lifecycle plus lock flag",
        CAPAssessmentDisposition.REFINE,
        "The lifecycle is sound but lacks an explicit rejected state and clearer locked semantics.",
        "Formalise candidate, approved, locked, rejected and archived governance without silent promotion.",
    ),
    CAPCapabilityAssessment(
        "reference.file-management",
        "Managed reference files and provenance/hash metadata",
        CAPAssessmentDisposition.KEEP,
        "VSCS must safely register and preserve externally authored canonical masters.",
        "Imported references retain provenance, integrity metadata and project-managed paths.",
    ),
    CAPCapabilityAssessment(
        "reference.gallery-preview",
        "Canonical reference gallery and preview",
        CAPAssessmentDisposition.KEEP,
        "Human visual review remains necessary for canonical governance.",
        "Gallery exposes role, lifecycle, provenance and readiness without authoring new masters.",
    ),
    CAPCapabilityAssessment(
        "reference.delete",
        "Reference deletion",
        CAPAssessmentDisposition.REFINE,
        "Hard deletion is unsafe for previously approved or locked production references.",
        "Prefer archive/history preservation; only unapproved disposable imports may be physically removed.",
    ),
    CAPCapabilityAssessment(
        "reference.technical-evaluation",
        "Evaluate Selected Image",
        CAPAssessmentDisposition.REFINE,
        "Technical QC can add value but must not become a second canonical authority.",
        "Retain as optional non-authoritative quality validation for imported master references.",
    ),
    CAPCapabilityAssessment(
        "reference.semantic-evaluation",
        "Semantic Evaluate Selected",
        CAPAssessmentDisposition.REFINE,
        "Semantic comparison can detect drift but is not allowed to create or redefine canon.",
        "Retain only as optional advisory compliance checking against approved CAP facts/constraints.",
    ),
    CAPCapabilityAssessment(
        "reference.generate-master",
        "Generate Canonical Images",
        CAPAssessmentDisposition.REMOVE,
        "Master reference authoring is already assigned to the approved ChatGPT workflow.",
        "VSCS imports and governs master references instead of competing with the authoring workflow.",
    ),
    CAPCapabilityAssessment(
        "reference.regenerate-feedback",
        "Regenerate canonical reference from feedback",
        CAPAssessmentDisposition.REMOVE,
        "It duplicates external master-reference authoring and creates two competing sources of truth.",
        "Feedback belongs to the external ChatGPT authoring cycle; the returned master is re-imported/versioned.",
    ),
    CAPCapabilityAssessment(
        "cap.ai-draft-generation",
        "Generate CAP Draft Package from pasted story context",
        CAPAssessmentDisposition.REPLACE,
        "Production stages should not independently re-read pasted manuscript context after Story Intelligence exists.",
        "Draft assistance, if retained, must consume approved Story Intelligence/XPD facts and remain moderator-controlled.",
    ),
    CAPCapabilityAssessment(
        "cap.production-readiness",
        "Single Production Readiness assessment",
        CAPAssessmentDisposition.REPLACE,
        "One readiness result cannot distinguish identity completeness from visual/generation readiness.",
        "Expose separate identity, reference, planning and generation readiness gates with reasons.",
    ),
)


CAP_PRODUCTION_CONTRACT_GAPS: tuple[CAPContractGap, ...] = (
    CAPContractGap(
        "gap.structured-facts",
        "Structured canonical facts and invariants",
        "Downstream consumers need stable facts without parsing free-form prose.",
    ),
    CAPContractGap(
        "gap.functional-identity",
        "Functional/behavioural identity",
        "Canonical capability must be separated from one story scene's action.",
    ),
    CAPContractGap(
        "gap.constraints",
        "Explicit canonical constraints / prohibited variations",
        "Prompt compilation needs machine-consumable boundaries on what may not change or be invented.",
    ),
    CAPContractGap(
        "gap.reference-view-role",
        "Reference viewpoint / production role taxonomy",
        "Primary/secondary importance cannot select front, side, top, detail or variant references for a shot.",
    ),
    CAPContractGap(
        "gap.category-reference-rules",
        "Category-specific required/optional reference sets",
        "Ships, characters, locations and props require different reference coverage before generation.",
    ),
    CAPContractGap(
        "gap.reference-origin",
        "Explicit reference origin/authoring provenance",
        "The contract must record externally authored ChatGPT master references without implying VSCS created them.",
    ),
    CAPContractGap(
        "gap.reference-selection",
        "Deterministic downstream reference-selection contract",
        "Shot planning/prompt compilation need a stable method to request appropriate references by camera/view need.",
    ),
    CAPContractGap(
        "gap.readiness-gates",
        "Separate identity, reference, planning and generation readiness gates",
        "Planning must continue when identity is known even if visual references are not yet generation-ready.",
    ),
    CAPContractGap(
        "gap.variant-contract",
        "Canonical variant handling",
        "Uniforms, states, interiors and approved alternates need explicit identities rather than unstructured supplementary images.",
    ),
    CAPContractGap(
        "gap.production-projection",
        "Read-only CAP production projection/API",
        "Production Planning should consume a stable contract instead of reaching into CAP editor persistence details.",
    ),
)


def disposition_counts() -> dict[CAPAssessmentDisposition, int]:
    """Return deterministic audit totals for reporting and regression tests."""
    return {
        disposition: sum(item.disposition is disposition for item in CAP_CAPABILITY_ASSESSMENTS)
        for disposition in CAPAssessmentDisposition
    }


def blocking_gaps() -> tuple[CAPContractGap, ...]:
    """Return gaps that must be closed before the Production Planning contract is final."""
    return tuple(
        gap for gap in CAP_PRODUCTION_CONTRACT_GAPS if gap.required_before_production_planning
    )
