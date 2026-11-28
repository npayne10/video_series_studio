"""W2.5.1: only superseded, source-grounded values may be replaced offline."""

import json

import pytest

from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DetailDecision,
    DetailOrigin,
)
from vscs.application.caps.design_revision import REVISION_HISTORY_KEY, REVISION_REFRESH_KEY
from vscs.application.caps.revision_reconciliation import (
    REVISION_RECONCILED_KEY,
    plan_revision_reconciliation,
)
from vscs.application.caps.structured_knowledge import StructuredKnowledgeProposal
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalConstraintKind,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    StructuredCAPKnowledge,
)

OLD = "a chamfer-cornered worktop"
NEW = "a square-cornered worktop with short raised side returns"
SOURCE = "reviewed-cap-specification:old"


def _scenario():
    spec = CAPStructuredSpecification(
        asset_id="CAP-PRP-001",
        category=AssetCategory.PROP,
        design_intent="A freestanding workstation",
        canonical_attributes={"components": NEW, "materials": "grey metal"},
        master_prompt="Unapproved design reference",
    )
    fields = [
        DesignFieldReview(
            field=key,
            proposed_value=value,
            final_value=value,
            decision=DetailDecision.EDIT if key == "components" else DetailDecision.ACCEPT,
            origin=DetailOrigin.OPERATOR_EDITED
            if key == "components"
            else DetailOrigin.DESIGN_PROPOSAL,
        ).model_dump(mode="json")
        for key, value in spec.canonical_attributes.items()
    ]
    metadata = {
        SPECIFICATION_METADATA_KEY: spec.model_dump_json(),
        DESIGN_REVIEW_KEY: json.dumps(
            {
                "version": 1,
                "base_fingerprint": "previous",
                "result_fingerprint": spec.fingerprint(),
                "reviewer": "Neill",
                "fields": fields,
                "canon_approved": False,
                "image_authorized": False,
            }
        ),
        REVISION_HISTORY_KEY: json.dumps(
            [
                {
                    "field": "components",
                    "old_value": OLD,
                    "new_value": NEW,
                }
            ]
        ),
        REVISION_REFRESH_KEY: json.dumps({"specification_fingerprint": spec.fingerprint()}),
        "classification": "keep me",
    }
    existing = StructuredCAPKnowledge(
        facts=(
            PersistedCanonicalFact(key="components", value=OLD, source=SOURCE),
            PersistedCanonicalFact(key="materials", value="grey metal", source=SOURCE),
            PersistedCanonicalFact(key="operator", value="independent note"),
        ),
        constraints=(
            PersistedCanonicalConstraint(
                kind=CanonicalConstraintKind.REQUIRED,
                rule=f"Preserve reviewed components: {OLD}",
                source=SOURCE,
            ),
            PersistedCanonicalConstraint(
                kind=CanonicalConstraintKind.REQUIRED,
                rule="Preserve independent lighting guidance",
                source="human",
            ),
        ),
        production_classifications=("prop",),
        production_metadata=metadata,
    )
    proposal = StructuredKnowledgeProposal(
        asset_id=spec.asset_id,
        source_summary=f"reviewed-cap-specification:{spec.fingerprint()}",
        knowledge=StructuredCAPKnowledge(
            facts=(
                PersistedCanonicalFact(
                    key="components",
                    value=NEW,
                    authority=KnowledgeAuthority.PROPOSED,
                ),
            ),
            constraints=(
                PersistedCanonicalConstraint(
                    kind=CanonicalConstraintKind.REQUIRED,
                    rule=f"Preserve reviewed components: {NEW}",
                    authority=KnowledgeAuthority.PROPOSED,
                ),
            ),
        ),
        visual_identity=f"Components: {NEW}",
        production_notes=f"Preserve reviewed components: {NEW}",
    )
    return metadata, existing, proposal


def test_reconciliation_preserves_unrelated_approved_data_and_does_not_write():
    metadata, existing, proposal = _scenario()
    copy = dict(metadata)
    plan = plan_revision_reconciliation(
        metadata,
        existing,
        proposal,
        f"Components: {OLD}\nMaterials: grey metal",
        f"Maintain production identity.\nPreserve reviewed components: {OLD}",
    )
    assert metadata == copy
    assert {x.key: x.value for x in plan.knowledge.facts} == {
        "components": NEW,
        "materials": "grey metal",
        "operator": "independent note",
    }
    assert plan.knowledge.production_classifications == ("prop",)
    assert any(
        x.rule == "Preserve independent lighting guidance" for x in plan.knowledge.constraints
    )
    assert not any(OLD in x.rule for x in plan.knowledge.constraints)
    assert "square-cornered" in plan.visual_identity
    assert "Materials: grey metal" in plan.visual_identity
    assert "Maintain production identity." in plan.production_notes
    assert len(plan.changes) == 4


def test_conflicting_operator_fact_blocks_reconciliation():
    metadata, existing, proposal = _scenario()
    changed = existing.facts[0].model_copy(update={"value": "independently authored detail"})
    existing = existing.model_copy(update={"facts": (changed, *existing.facts[1:])})
    with pytest.raises(ValueError, match="Conflicting authored fact"):
        plan_revision_reconciliation(metadata, existing, proposal, "", "")


def test_stale_fingerprint_blocks_reconciliation():
    metadata, existing, proposal = _scenario()
    metadata[REVISION_REFRESH_KEY] = '{"specification_fingerprint":"outdated"}'
    with pytest.raises(ValueError, match="changed"):
        plan_revision_reconciliation(metadata, existing, proposal, "", "")


def test_ambiguous_guidance_blocks_reconciliation():
    metadata, existing, proposal = _scenario()
    with pytest.raises(ValueError, match="ambiguous old requirement"):
        plan_revision_reconciliation(
            metadata,
            existing,
            proposal,
            f"Artist altered {OLD} and notes must be reviewed",
            "",
        )


def test_reconciliation_preview_shows_before_and_after(qtbot):
    from PySide6.QtWidgets import QTableWidget

    from vscs.presentation.widgets.cap_structured_knowledge import (
        CAPRevisionReconciliationDialog,
    )

    metadata, existing, proposal = _scenario()
    plan = plan_revision_reconciliation(
        metadata,
        existing,
        proposal,
        f"Components: {OLD}",
        f"Preserve reviewed components: {OLD}",
    )
    dialog = CAPRevisionReconciliationDialog(plan)
    qtbot.addWidget(dialog)
    table = dialog.findChild(QTableWidget, "capRevisionReconciliationPreview")
    assert table is not None
    assert table.rowCount() == len(plan.changes)
    assert any(OLD in table.item(row, 1).text() for row in range(table.rowCount()))
    assert any(NEW in table.item(row, 2).text() for row in range(table.rowCount()))
    assert table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers


def test_second_revision_uses_only_unreconciled_history():
    metadata, existing, proposal = _scenario()
    metadata[REVISION_HISTORY_KEY] = json.dumps(
        [
            {"field": "components", "old_value": "very old design", "new_value": OLD},
            {"field": "components", "old_value": OLD, "new_value": NEW},
        ]
    )
    metadata[REVISION_RECONCILED_KEY] = json.dumps({"history_count": 1})
    plan = plan_revision_reconciliation(metadata, existing, proposal, f"Components: {OLD}", "")
    assert plan.knowledge.facts[0].value == NEW
    assert all("very old design" not in row[1] for row in plan.changes)
