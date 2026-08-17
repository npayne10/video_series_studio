from __future__ import annotations

from types import SimpleNamespace

import pytest

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionTaskCompilationContext,
    ProductionTaskCompilationError,
    ProductionTaskCompilerService,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionStatus,
)


class _UniversalStub:
    def __init__(self, *, ready: bool = True, current: bool = True) -> None:
        self.ready = ready
        self.current = current

    def draft(self, shot_id: str) -> object:
        return SimpleNamespace(
            shot_id=shot_id,
            status=(
                UniversalProductionDescriptionStatus.READY
                if self.ready
                else UniversalProductionDescriptionStatus.DRAFT
            ),
        )

    def is_current(self, _draft: object) -> bool:
        return self.current


class _PackageStub:
    def __init__(self) -> None:
        self.package = SimpleNamespace(
            package_id="PP-SH027-ABC123",
            validation={
                "universal_description_complete": True,
                "cross_authority_consistent": True,
            },
            universal_description={
                "production": {
                    "current_shot_id": "SH027",
                    "provider_neutral": True,
                    "canonical_references": [
                        {
                            "asset_id": "CAP-CHR-001",
                            "canonical_reference": "refs/james-front.png",
                        },
                        {
                            "asset_id": "CAP-SHP-001",
                            "canonical_reference": "refs/mauritania.png",
                        },
                    ],
                }
            },
        )

    def require_current_package(self, _shot_id: str) -> object:
        return self.package


def _context(*, revision: int = 3) -> ProductionTaskCompilationContext:
    return ProductionTaskCompilationContext(
        production_id="production-XORIX-S01",
        episode_id="EP01",
        scene_id="SC04",
        approved_by="Neill",
        authority_revision=revision,
    )


def _compiler(*, ready: bool = True, current: bool = True) -> ProductionTaskCompilerService:
    return ProductionTaskCompilerService(  # type: ignore[arg-type]
        _UniversalStub(ready=ready, current=current),
        _PackageStub(),
    )


def test_compiles_ready_current_upd_into_provider_neutral_video_task() -> None:
    task = _compiler().compile_shot("sh027", _context())[0]

    assert task.shot_id == "SH027"
    assert task.scene_id == "SC04"
    assert task.task_type is ProductionTaskType.VIDEO_GENERATION
    assert task.capabilities == (ProductionCapability.VIDEO_GENERATION,)
    assert task.expected_outputs == ("video/shot",)
    assert task.state is ProductionTaskState.PLANNED
    assert task.authority.authority_id == "UPD-SH027"
    assert task.authority.revision == 3
    assert task.authority.approved_by == "Neill"
    assert not hasattr(task, "provider")
    assert not hasattr(task, "workflow")


def test_compilation_is_deterministic_for_same_authority_revision_and_fingerprint() -> None:
    compiler = _compiler()

    first = compiler.compile_shot("SH027", _context())[0]
    second = compiler.compile_shot("SH027", _context())[0]
    changed_revision = compiler.compile_shot("SH027", _context(revision=4))[0]

    assert first.task_id == second.task_id
    assert first.authority.fingerprint == second.authority.fingerprint
    assert changed_revision.task_id != first.task_id


def test_compiler_preserves_canonical_reference_inputs_without_provider_detail() -> None:
    task = _compiler().compile_shot("SH027", _context())[0]

    assert task.required_inputs == (
        "canonical-reference:CAP-CHR-001:refs/james-front.png",
        "canonical-reference:CAP-SHP-001:refs/mauritania.png",
    )
    assert dict(task.provenance) == {
        "source_authority": "universal-production-description",
        "source_package_id": "PP-SH027-ABC123",
    }


def test_compiler_rejects_unready_or_stale_upd() -> None:
    with pytest.raises(ProductionTaskCompilationError, match="not Ready"):
        _compiler(ready=False).compile_shot("SH027", _context())

    with pytest.raises(ProductionTaskCompilationError, match="stale"):
        _compiler(current=False).compile_shot("SH027", _context())
