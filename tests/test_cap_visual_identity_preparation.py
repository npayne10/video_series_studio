"""B.5.26 offline visual MASTER candidate preparation and governance boundaries."""

from types import SimpleNamespace

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
)
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.application.caps.visual_identity_preparation import prepare_visual_identity
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus, CanonicalReferenceView
from vscs.presentation.widgets.cap_visual_identity_preparation import (
    VisualIdentityPreparationDialog,
)


def _cap(
    category: AssetCategory,
    values: dict[str, str],
    *,
    deferred: tuple[str, ...] = (),
    status: CAPStatus = CAPStatus.DRAFT,
):
    deferred = tuple(
        dict.fromkeys(
            (*deferred, *(key for key in REQUIRED_FIELDS[category] if key not in values))
        )
    )
    spec = CAPStructuredSpecification(
        asset_id="STORY-TEST-001",
        category=category,
        design_intent=f"An existing {category.value} asset",
        canonical_attributes={
            **values,
            **{field: "Unresolved" for field in deferred},
        },
        master_prompt="Provider output, not approved.",
        continuity_rules=("Containment is a separate relationship.",),
    )
    reviews = tuple(
        DesignFieldReview(
            field=field,
            proposed_value=value,
            final_value=value,
            decision=DetailDecision.ACCEPT,
            origin=DetailOrigin.DESIGN_PROPOSAL,
        )
        for field, value in values.items()
    ) + tuple(
        DesignFieldReview(
            field=field,
            proposed_value="Unresolved",
            decision=DetailDecision.DEFER,
            origin=DetailOrigin.UNRESOLVED,
        )
        for field in deferred
    )
    package = DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        fields=reviews,
        reviewer="Operator",
    )
    reviewed, audit = apply_review(spec, package)
    from vscs.application.caps.design_completion import build_reviewed_master_prompt

    reviewed = reviewed.model_copy(
        update={"master_prompt": build_reviewed_master_prompt(reviewed, package)}
    )
    return SimpleNamespace(
        asset_id=spec.asset_id,
        title=category.value.title() + " acceptance asset",
        status=status,
        production_metadata={
            SPECIFICATION_METADATA_KEY: reviewed.model_dump_json(),
            DESIGN_REVIEW_KEY: audit,
        },
    )


def _prepare(cap):
    return prepare_visual_identity(
        cap,
        (CanonicalReferenceView.MASTER, CanonicalReferenceView.FRONT),
        (),
    )


def test_deferred_ship_silhouette_blocks_master_and_never_invents_one():
    cap = _cap(
        AssetCategory.SHIP,
        {
            "dimensions": "Proposed 48 m long, 18 m wide, 12 m high.",
            "hull": "Layered metallic pressure shell.",
            "markings": "Maintenance labels.",
        },
        deferred=("silhouette",),
    )
    plan = _prepare(cap)
    assert not plan.ready_for_master_candidate
    assert plan.provider_calls == 0
    assert "Ship visual identity is unresolved" in " ".join(plan.blockers)
    assert "48 m" in plan.master_candidate_prompt
    assert "invented silhouette" in plan.negative_prompt
    assert "silhouette" in plan.deferred_fields
    assert "silhouette:" not in plan.master_candidate_prompt
    assert plan.missing_reference_views == (
        CanonicalReferenceView.MASTER,
        CanonicalReferenceView.FRONT,
    )


def test_reviewed_location_layout_is_candidate_preparable_offline():
    cap = _cap(
        AssetCategory.LOCATION,
        {"layout": "Proposed rectangular room with fixed workstation."},
        deferred=("architecture",),
    )
    plan = _prepare(cap)
    assert plan.ready_for_master_candidate
    assert plan.provider_calls == 0
    assert "rectangular room" in plan.master_candidate_prompt
    assert "architecture:" not in plan.master_candidate_prompt
    assert plan.specification_fingerprint
    assert plan.review_fingerprint


def test_reviewed_console_components_can_anchor_candidate_without_deferred_geometry():
    cap = _cap(
        AssetCategory.PROP,
        {"components": "Three buttons, blue display and rotary dial."},
        deferred=("geometry",),
    )
    plan = _prepare(cap)
    assert plan.ready_for_master_candidate
    assert "three buttons" in plan.master_candidate_prompt.lower()
    assert "geometry:" not in plan.master_candidate_prompt


def test_missing_review_blocks_preparation():
    cap = SimpleNamespace(
        asset_id="STORY-SHI-001",
        title="Unreviewed ship",
        status=CAPStatus.DRAFT,
        production_metadata={},
    )
    plan = _prepare(cap)
    assert not plan.ready_for_master_candidate
    assert "missing" in " ".join(plan.blockers).lower()
    assert plan.provider_calls == 0


def test_tampered_rejected_field_blocks_candidate():
    cap = _cap(AssetCategory.SHIP, {"hull": "Metallic hull"}, deferred=("silhouette",))
    import json

    raw = json.loads(cap.production_metadata[SPECIFICATION_METADATA_KEY])
    raw["canonical_attributes"]["silhouette"] = "Invented needle hull"
    cap.production_metadata[SPECIFICATION_METADATA_KEY] = json.dumps(raw)
    plan = _prepare(cap)
    assert not plan.ready_for_master_candidate
    assert "unexpectedly persisted" in " ".join(plan.blockers)


def test_non_draft_cap_cannot_use_draft_preparation():
    cap = _cap(AssetCategory.LOCATION, {"layout": "Proposed fixed room layout"})
    cap.status = CAPStatus.APPROVED
    assert not _prepare(cap).ready_for_master_candidate


def test_prep_dialog_is_read_only_and_disables_copy_when_blocked(qtbot):
    cap = _cap(AssetCategory.SHIP, {"hull": "Metal hull"}, deferred=("silhouette",))
    dialog = VisualIdentityPreparationDialog(_prepare(cap))
    qtbot.addWidget(dialog)
    assert dialog.prompt_view.isReadOnly()
    assert dialog.blockers_view.isReadOnly()
    assert not dialog.copy_button.isEnabled()
    assert "BLOCKED" in dialog.status_label.text()


def test_prep_dialog_allows_copy_for_nonblocked_candidate(qtbot):
    cap = _cap(AssetCategory.LOCATION, {"layout": "Fixed rectangular room"})
    dialog = VisualIdentityPreparationDialog(_prepare(cap))
    qtbot.addWidget(dialog)
    assert dialog.copy_button.isEnabled()
    assert "not approved" in dialog.status_label.text().lower()


def test_active_master_reference_blocks_duplicate_candidate_preparation():
    cap = _cap(AssetCategory.LOCATION, {"layout": "Fixed room with console"})
    prepared = prepare_visual_identity(
        cap,
        (CanonicalReferenceView.MASTER, CanonicalReferenceView.PRIMARY_THREE_QUARTER),
        (CanonicalReferenceView.MASTER,),
    )
    assert not prepared.ready_for_master_candidate
    assert "active MASTER" in " ".join(prepared.blockers)
    assert prepared.missing_reference_views == (CanonicalReferenceView.PRIMARY_THREE_QUARTER,)


def test_visual_preparation_does_not_modify_persisted_cap_metadata():
    cap = _cap(AssetCategory.PROP, {"components": "Three buttons and one rotary dial."})
    before = dict(cap.production_metadata)
    _prepare(cap)
    assert cap.production_metadata == before


def test_invalid_approval_flag_blocks_preparation():
    import json

    cap = _cap(AssetCategory.LOCATION, {"layout": "Fixed room"})
    raw = json.loads(cap.production_metadata[DESIGN_REVIEW_KEY])
    raw["image_authorized"] = True
    cap.production_metadata[DESIGN_REVIEW_KEY] = json.dumps(raw)
    result = _prepare(cap)
    assert not result.ready_for_master_candidate
    assert "approval authority" in " ".join(result.blockers)
