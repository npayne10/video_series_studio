"""Regression tests for the public rendering package API."""

from __future__ import annotations

import vscs.application.rendering as rendering


def test_rendering_public_api_exports_every_public_binding() -> None:
    exported = set(rendering.__all__)
    public_bindings = {
        name
        for name in vars(rendering)
        if not name.startswith("_")
    }

    assert len(rendering.__all__) == len(exported)
    assert exported == public_bindings
    assert all(hasattr(rendering, name) for name in rendering.__all__)
