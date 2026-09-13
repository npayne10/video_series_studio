"""Regression coverage for Phase 20.18.2 compile authority defects."""

from __future__ import annotations

import json
from types import SimpleNamespace

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)
from vscs.infrastructure.production_execution.current_authority_backend import (
    _CurrentProductionPackageStore,
)
from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LocalLTX23V721ProductionPackageCompilationService,
)


def test_compiler_recovers_persisted_governed_reference_plan(tmp_path) -> None:
    """A historical UPD without an embedded plan still compiles governed references."""
    plan = {
        "schema_version": "1.1",
        "references": [
            {
                "semantic_role": "primary_identity",
                "asset_id": "CAP-CHR-001",
                "relative_path": "references/james.png",
            }
        ],
    }
    production = tmp_path / "production"
    production.mkdir()
    (production / "governed_reference_plans.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "governed_reference_plans": [
                    {
                        "shot_id": "EP-001-SCN-001-SHT-002",
                        "reference_plan": plan,
                        "provenance": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    compiler = ProductionPackageCompilerService(reference_root=tmp_path)

    assert compiler._reference_plan_payload({}, "ep-001-scn-001-sht-002") == plan


def test_ready_upd_source_package_pin_prevents_latest_package_dialogue_drift(
    tmp_path, monkeypatch
) -> None:
    """READY-UPD execution resolves its reviewed package, not the latest shot record."""
    store = _CurrentProductionPackageStore(tmp_path)
    approved = SimpleNamespace(
        package_id="PP-APPROVED",
        shot_id="EP-001-SCN-001-SHT-002",
    )
    later = SimpleNamespace(
        package_id="PP-LATER",
        shot_id="EP-001-SCN-001-SHT-002",
    )
    records = (
        {
            "package_id": approved.package_id,
            "shot_id": approved.shot_id,
        },
        {
            "package_id": later.package_id,
            "shot_id": later.shot_id,
        },
    )
    monkeypatch.setattr(store, "_raw_packages", lambda: records)

    def canonical(raw):
        return approved if raw["package_id"] == approved.package_id else later

    monkeypatch.setattr(
        LocalLTX23V721ProductionPackageCompilationService,
        "_canonical_from_dict",
        staticmethod(canonical),
    )

    assert store.current_package(approved.shot_id) is later

    store.pin_source_package(approved.package_id)

    assert store.current_package(approved.shot_id) is approved
