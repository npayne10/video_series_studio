"""Phase 20.18.2 governed UPD approval-provenance regressions."""

from __future__ import annotations

from types import MethodType, SimpleNamespace
from typing import Any

from vscs.application.universal_approval_provenance import (
    UniversalProductionDescriptionApprovalStore,
    install_universal_approval_provenance,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionDraft,
    UniversalProductionDescriptionStatus,
)


def _ready_draft(
    *,
    reference_path: str = "CAP-CHR-001-Master-V2.png",
    action: str = "Sandra reports unusual data to James.",
) -> UniversalProductionDescriptionDraft:
    return UniversalProductionDescriptionDraft(
        shot_id="EP-001-SCN-001-SHT-001",
        source_package_id="PP-CURRENT",
        dependency_fingerprint="dependency",
        description={
            "current_shot_id": "EP-001-SCN-001-SHT-001",
            "action_performance": {"temporal_narrative": action},
            "provider_neutral": True,
            "universal_text": action,
            "reference_plan": {
                "bindings": [
                    {
                        "asset_id": "CAP-CHR-001",
                        "file_path": reference_path,
                    }
                ]
            },
        },
        status=UniversalProductionDescriptionStatus.READY,
    )


def _projects(tmp_path: Any) -> Any:
    return SimpleNamespace(project_directory=tmp_path)


def test_upd_approval_survives_governed_reference_only_refresh(tmp_path: Any) -> None:
    store = UniversalProductionDescriptionApprovalStore(_projects(tmp_path))
    original = _ready_draft(reference_path="CAP-CHR-001-Master-V1.png")
    refreshed = _ready_draft(reference_path="CAP-CHR-001-Master-V2.png")

    approval = store.establish(original, "Neill")

    assert store.current_for(refreshed) == approval


def test_upd_approval_invalidates_when_reviewed_authority_changes(tmp_path: Any) -> None:
    store = UniversalProductionDescriptionApprovalStore(_projects(tmp_path))
    original = _ready_draft()
    changed = _ready_draft(action="James orders an immediate course change.")

    store.establish(original, "Neill")

    assert store.current_for(changed) is None


def test_compiled_upd_carries_structured_and_compatibility_approval_fields(tmp_path: Any) -> None:
    install_universal_approval_provenance()
    draft = _ready_draft()
    projects = _projects(tmp_path)
    store = UniversalProductionDescriptionApprovalStore(projects)
    approval = store.establish(draft, "Neill")

    service = UniversalProductionDescriptionCompilerService.__new__(
        UniversalProductionDescriptionCompilerService
    )
    service.projects = projects
    service.packages = SimpleNamespace()
    service.reference_plans = SimpleNamespace()
    service._require_draft = MethodType(lambda self, shot_id: draft, service)
    service.is_current = MethodType(lambda self, current: True, service)
    service._require_upstream_ready = MethodType(lambda self, shot_id: None, service)
    service._require_consistent = MethodType(lambda self, value: None, service)
    service._validate = MethodType(lambda self, value: None, service)
    service._compile_description = MethodType(
        lambda self, value: {"governed": dict(value), "production": dict(value)},
        service,
    )
    service._derive = MethodType(
        lambda self, shot_id, compiled, production_notes="": compiled,
        service,
    )

    compiled = service.compile(draft.shot_id)

    assert compiled["approved_by"] == "Neill"
    assert compiled["approved_at"] == approval.approved_at
    assert compiled["approval"] == {
        "approved_by": "Neill",
        "approved_at": approval.approved_at,
        "reviewed_authority_fingerprint": approval.reviewed_authority_fingerprint,
    }
