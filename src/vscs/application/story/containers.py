"""Production-container identities for episodic and promotional story content."""

from __future__ import annotations

import re
from enum import StrEnum


class ProductionContainerType(StrEnum):
    """Supported story containers that can own scenes."""

    EPISODE = "episode"
    TRAILER = "trailer"
    TEASER = "teaser"
    PROMO = "promo"
    TEST = "test"
    SPECIAL = "special"

    @property
    def label(self) -> str:
        """Return a readable UI label."""
        return self.value.title()

    @property
    def default_id(self) -> str:
        """Return the initial canonical ID for this container type."""
        return {
            ProductionContainerType.EPISODE: "EP-001",
            ProductionContainerType.TRAILER: "T01",
            ProductionContainerType.TEASER: "TEASER-01",
            ProductionContainerType.PROMO: "PROMO-01",
            ProductionContainerType.TEST: "TEST-01",
            ProductionContainerType.SPECIAL: "SPECIAL-01",
        }[self]


def infer_container_type(container_id: str) -> ProductionContainerType:
    """Infer a container type from a legacy or current container ID."""
    normalized = container_id.strip().upper()
    if normalized.startswith("EP-"):
        return ProductionContainerType.EPISODE
    if normalized.startswith(("T", "TR-", "TRAILER-")):
        return ProductionContainerType.TRAILER
    if normalized.startswith("TEASER-"):
        return ProductionContainerType.TEASER
    if normalized.startswith("PROMO-"):
        return ProductionContainerType.PROMO
    if normalized.startswith("TEST-"):
        return ProductionContainerType.TEST
    if normalized.startswith("SPECIAL-"):
        return ProductionContainerType.SPECIAL
    return ProductionContainerType.SPECIAL


def normalize_container_id(value: str, container_type: ProductionContainerType) -> str:
    """Normalize a user-entered container identity without changing its meaning."""
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").upper()
    return normalized or container_type.default_id


def build_scene_id(container_id: str, sequence_number: int) -> str:
    """Build a stable scene ID from a generic production container."""
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", container_id.strip()).strip("-")
    normalized = normalized.upper() or ProductionContainerType.EPISODE.default_id
    return f"{normalized}-SCN-{sequence_number:03d}"
