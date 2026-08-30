from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LTX23_V721_PACKAGE_SCHEMA,
    LocalLTX23V721ProductionPackageCompilationService,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def test_v721_validator_forces_recompile_of_old_provider_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "production_package.json"
    path.write_text(json.dumps({"schema_version": "7.1.4-vscs-1"}), encoding="utf-8")
    monkeypatch.setattr(
        LocalProductionPackageCompilationService,
        "validate_file",
        lambda self, task, package_path: None,
    )
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    with pytest.raises(LocalProductionPackageCompilationError, match="recompile"):
        service.validate_file(object(), path)  # type: ignore[arg-type]


def test_v721_validator_accepts_current_provider_package_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "production_package.json"
    path.write_text(json.dumps({"schema_version": LTX23_V721_PACKAGE_SCHEMA}), encoding="utf-8")
    monkeypatch.setattr(
        LocalProductionPackageCompilationService,
        "validate_file",
        lambda self, task, package_path: None,
    )
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    service.validate_file(object(), path)  # type: ignore[arg-type]
