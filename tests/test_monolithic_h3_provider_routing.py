"""Protect selected MiniMax H3 from legacy monolithic backend execution."""

from types import SimpleNamespace

import pytest

from vscs.application.production_execution import ProductionExecutionError
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LocalComfyUIProductionExecutionBackend,
)
from vscs.infrastructure.production_execution.provider_policy_profiles import (
    MINIMAX_H3_POLICY_PROFILE_ID,
)


@pytest.mark.parametrize("profile", ["production", "preview", "master"])
def test_selected_h3_cannot_use_legacy_start_for_profile(profile):
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.provider_policy_selections = SimpleNamespace(
        selected_profile=lambda task_id, selected_profile: SimpleNamespace(
            profile_id=MINIMAX_H3_POLICY_PROFILE_ID
        )
    )

    with pytest.raises(ProductionExecutionError, match="not legacy monolithic"):
        backend.start_for_profile("PT-H3", profile=profile)


def test_selected_h3_cannot_use_legacy_start():
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.provider_policy_selections = SimpleNamespace(
        selected_profile=lambda task_id, profile: SimpleNamespace(
            profile_id=MINIMAX_H3_POLICY_PROFILE_ID
        )
    )

    with pytest.raises(ProductionExecutionError, match="not legacy monolithic"):
        backend.start("PT-H3")
