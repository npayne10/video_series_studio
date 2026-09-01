"""Phase 20.18.2 governed production-package runtime regressions."""

from __future__ import annotations

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)


def test_production_package_derives_frames_from_governed_shot_runtime() -> None:
    settings = ProductionPackageCompilerService._render_settings(
        {
            "shot": {"target_runtime_seconds": 22},
            "render": {"fps": 24},
        },
        "production",
    )

    assert settings["frames_per_second"] == 24
    assert settings["frame_count"] == 528


def test_explicit_governed_frame_count_overrides_runtime_derivation() -> None:
    settings = ProductionPackageCompilerService._render_settings(
        {
            "shot": {"target_runtime_seconds": 22, "frame_count": 240},
            "render": {"fps": 24},
        },
        "production",
    )

    assert settings["frame_count"] == 240


def test_action_performance_runtime_is_used_when_shot_runtime_is_unavailable() -> None:
    settings = ProductionPackageCompilerService._render_settings(
        {
            "shot": {},
            "action_performance": {"duration_seconds": 10.5},
            "render": {"frames_per_second": 24},
        },
        "production",
    )

    assert settings["frame_count"] == 252
