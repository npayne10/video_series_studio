"""Provider-specific governed multi-reference contract for LTX 2.3.

Phase 20.18.2 originally collapsed multiple governed references into a synthetic
horizontal contact sheet. That preserved provenance but incorrectly turned the helper
image into scene composition authority. Production execution now preserves each
governed reference separately and emits an explicit LTX Ingredients / IC-LoRA
multi-reference contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .package_compilation import LocalProductionPackageCompilationError

_LEGACY_HELPER_ROLES = frozenset({"scene_composition_anchor", "provider_helper_reference"})
_ROLE_ORDER = {
    "primary_identity": 0,
    "secondary_identity": 1,
    "group_identity": 2,
    "environment_reference": 3,
}


class GovernedProviderReferenceHelperBuilder:
    """Preserve governed references and emit the provider multi-reference contract.

    The historical class name is retained to avoid changing the current-authority
    composition seam. It no longer creates image helpers.
    """

    ROOT = Path("production") / "provider_reference_helpers"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)

    def ensure_helper(self, plan: dict[str, Any]) -> dict[str, Any]:
        bindings_raw = plan.get("bindings")
        if not isinstance(bindings_raw, list):
            raise LocalProductionPackageCompilationError(
                "Provider ReferencePlan bindings must be a JSON array"
            )

        bindings = [
            dict(item)
            for item in bindings_raw
            if isinstance(item, dict) and str(item.get("role") or "") not in _LEGACY_HELPER_ROLES
        ]
        required = [item for item in bindings if item.get("required") is True]
        if not required:
            raise LocalProductionPackageCompilationError(
                "LTX provider reference contract requires at least one governed reference"
            )
        if len(required) > 3:
            raise LocalProductionPackageCompilationError(
                "LTX Ingredients production workflow supports at most three required governed "
                "references per shot"
            )

        ordered = sorted(required, key=self._reference_sort_key)
        enriched = dict(plan)
        enriched["bindings"] = bindings

        references_raw = enriched.get("references")
        if isinstance(references_raw, list):
            enriched["references"] = [
                dict(item)
                for item in references_raw
                if isinstance(item, dict)
                and str(item.get("role") or "") not in _LEGACY_HELPER_ROLES
                and str(item.get("reference_class") or "") != "provider_specific_helper"
            ]

        enriched.pop("provider_helper", None)
        enriched["provider_multi_reference"] = {
            "schema_version": "1.0",
            "enabled": True,
            "mode": "ltx_ingredients_iclora",
            "collapsed_scene_anchor": False,
            "reference_count": len(ordered),
            "references": [
                {
                    "slot": index,
                    "reference_id": str(item.get("reference_id") or ""),
                    "asset_id": str(item.get("asset_id") or ""),
                    "role": str(item.get("role") or ""),
                    "path": str(item.get("path") or ""),
                    "required": True,
                    "provider_ready": item.get("provider_ready") is True,
                    "file_checksum": item.get("file_checksum"),
                    "reference_fingerprint": item.get("reference_fingerprint"),
                }
                for index, item in enumerate(ordered, start=1)
            ],
            "continuity": None,
        }
        return enriched

    @staticmethod
    def _reference_sort_key(item: dict[str, Any]) -> tuple[int, str]:
        role = str(item.get("role") or "")
        return (_ROLE_ORDER.get(role, 100), str(item.get("reference_id") or ""))
