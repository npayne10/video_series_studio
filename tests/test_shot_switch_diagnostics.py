"""Verify shot-switch timing diagnostics remain opt-in and transparent."""

import logging

import pytest

from vscs.presentation.widgets.shot_switch_diagnostics import (
    measure_shot_switch,
    profile_selection_handler,
)


def test_shot_switch_profile_disabled_by_default(monkeypatch, caplog):
    monkeypatch.delenv("VSCS_SHOT_SWITCH_PROFILE", raising=False)
    with caplog.at_level(logging.WARNING), measure_shot_switch("selection.total"):
        pass
    assert "SHOT_SWITCH_PROFILE" not in caplog.text


def test_shot_switch_profile_records_stage(monkeypatch, caplog):
    monkeypatch.setenv("VSCS_SHOT_SWITCH_PROFILE", "1")
    with caplog.at_level(logging.WARNING), measure_shot_switch("scheduling.queue"):
        pass
    assert "SHOT_SWITCH_PROFILE stage=scheduling.queue duration_ms=" in caplog.text


def test_shot_switch_profile_preserves_errors(monkeypatch):
    monkeypatch.setenv("VSCS_SHOT_SWITCH_PROFILE", "1")
    with pytest.raises(RuntimeError, match="failure"), measure_shot_switch("selection.original"):
        raise RuntimeError("failure")


def test_deep_profile_disabled_is_transparent(monkeypatch, caplog):
    monkeypatch.delenv("VSCS_SHOT_SWITCH_PROFILE", raising=False)
    with caplog.at_level(logging.WARNING):
        result = profile_selection_handler(
            lambda value: value + 1, "selection.pre_scheduling_chain"
        )(4)
    assert result == 5
    assert "top_calls" not in caplog.text


def test_deep_profile_reports_top_calls(monkeypatch, caplog):
    monkeypatch.setenv("VSCS_SHOT_SWITCH_PROFILE", "1")
    with caplog.at_level(logging.WARNING):
        result = profile_selection_handler(lambda: 42, "selection.pre_scheduling_chain")()
    assert result == 42
    assert "top_calls stage=selection.pre_scheduling_chain" in caplog.text
