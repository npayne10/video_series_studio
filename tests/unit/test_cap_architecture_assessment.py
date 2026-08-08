"""Phase 18.2.11.1 CAP architecture assessment regression coverage."""

from vscs.application.caps import (
    CAP_CAPABILITY_ASSESSMENTS,
    CAP_PRODUCTION_CONTRACT_GAPS,
    MASTER_REFERENCE_AUTHORING_POLICY,
    CAPAssessmentDisposition,
    blocking_gaps,
    disposition_counts,
)


def test_every_assessed_capability_has_unique_identity_and_target_contract() -> None:
    capability_ids = [item.capability_id for item in CAP_CAPABILITY_ASSESSMENTS]

    assert len(capability_ids) == len(set(capability_ids))
    assert CAP_CAPABILITY_ASSESSMENTS
    assert all(item.capability.strip() for item in CAP_CAPABILITY_ASSESSMENTS)
    assert all(item.rationale.strip() for item in CAP_CAPABILITY_ASSESSMENTS)
    assert all(item.target_contract.strip() for item in CAP_CAPABILITY_ASSESSMENTS)


def test_assessment_exercises_all_rationalisation_dispositions() -> None:
    counts = disposition_counts()

    assert counts[CAPAssessmentDisposition.KEEP] > 0
    assert counts[CAPAssessmentDisposition.REFINE] > 0
    assert counts[CAPAssessmentDisposition.REPLACE] > 0
    assert counts[CAPAssessmentDisposition.REMOVE] > 0


def test_chatgpt_owns_master_while_vscs_may_generate_derived_references() -> None:
    by_id = {item.capability_id: item for item in CAP_CAPABILITY_ASSESSMENTS}

    assert "externally in ChatGPT" in MASTER_REFERENCE_AUTHORING_POLICY
    assert "derived production references" in MASTER_REFERENCE_AUTHORING_POLICY
    assert by_id["reference.generate-master"].disposition is CAPAssessmentDisposition.REPLACE
    assert "Generate Production References" in by_id["reference.generate-master"].target_contract
    assert by_id["reference.regenerate-feedback"].disposition is CAPAssessmentDisposition.REFINE
    assert by_id["reference.structured-registry"].disposition is CAPAssessmentDisposition.KEEP


def test_legacy_reference_paths_are_retired_in_favour_of_structured_references() -> None:
    by_id = {item.capability_id: item for item in CAP_CAPABILITY_ASSESSMENTS}

    assert by_id["cap.legacy-reference-paths"].disposition is CAPAssessmentDisposition.REMOVE
    assert by_id["reference.generic-role"].disposition is CAPAssessmentDisposition.REPLACE


def test_production_contract_gaps_are_unique_and_block_phase_18_3_contract() -> None:
    gap_ids = [gap.gap_id for gap in CAP_PRODUCTION_CONTRACT_GAPS]
    required = blocking_gaps()

    assert len(gap_ids) == len(set(gap_ids))
    assert required
    assert len(required) == len(CAP_PRODUCTION_CONTRACT_GAPS)
    assert {gap.gap_id for gap in required} >= {
        "gap.structured-facts",
        "gap.reference-view-role",
        "gap.category-reference-rules",
        "gap.reference-selection",
        "gap.readiness-gates",
        "gap.production-projection",
    }


def test_story_specific_notes_are_replaced_by_structured_contract_fields() -> None:
    by_id = {item.capability_id: item for item in CAP_CAPABILITY_ASSESSMENTS}

    assert by_id["cap.production-notes"].disposition is CAPAssessmentDisposition.REPLACE
    assert "functional identity" in by_id["cap.production-notes"].target_contract
    assert "canonical constraints" in by_id["cap.production-notes"].target_contract
