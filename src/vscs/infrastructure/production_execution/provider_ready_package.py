"""Provider-ready production package resolution for Phase 20.15.1a."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from typing import Any

from vscs.application.production_execution.package_compilation import CompiledProductionPackage


class ProviderReadyPackageResolutionError(ValueError):
    """Raised when governed production inputs cannot be resolved for provider execution."""


class ProviderReadyProductionPackageResolver:
    """Resolve project authority into provider-accessible visual and render contracts."""

    IDENTITY_CATEGORIES = frozenset({"character", "ship", "vehicle"})

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)

    def resolve(self, compiled: CompiledProductionPackage) -> dict[str, Any]:
        """Return provider-ready sections without changing approved production authority."""
        resolved_visual_assets = self._resolved_visual_assets(compiled)
        reference_plan = self._reference_plan(resolved_visual_assets, compiled)
        resolved_profiles = self._resolved_profiles(compiled)
        profile_prompt_instructions = [
            item["prompt_instructions"]
            for item in resolved_profiles
            if item.get("prompt_instructions")
        ]
        continuity = self._continuity_contract(compiled)
        timing = {
            "fps": compiled.frames_per_second,
            "frames": compiled.frame_count,
            "duration_seconds": compiled.duration_seconds,
        }
        generation = {
            "render_profile": compiled.profile,
            "width": compiled.width,
            "height": compiled.height,
            "cfg": compiled.cfg,
            "ic_lora_strength": compiled.ic_lora_strength,
            "seed": compiled.seed,
            "reference_architecture": "identity_first_minimal",
            "ic_lora_max_identity_references": reference_plan["ic_lora"][
                "maximum_identity_references"
            ],
        }
        output_prefix = (
            f"{compiled.production_id}/{compiled.episode_id}/{compiled.profile}/"
            f"{compiled.task_id}_{compiled.profile}"
        )
        output = {
            "root": f"{compiled.production_id}/{compiled.episode_id}/{compiled.profile}",
            "filename_prefix": output_prefix,
        }
        composition_plan = deepcopy(compiled.composition_plan)
        composition_plan["resolved_visual_assets"] = resolved_visual_assets
        composition_plan["reference_plan"] = reference_plan
        composition_plan["resolved_production_profiles"] = resolved_profiles
        composition_plan["profile_prompt_instructions"] = profile_prompt_instructions
        composition_plan["temporal_start_policy"] = continuity["temporal_start_policy"]
        composition_plan["provider_ready"] = True
        return {
            "resolved_visual_assets": resolved_visual_assets,
            "resolved_production_profiles": resolved_profiles,
            "profile_prompt_instructions": profile_prompt_instructions,
            "reference_plan": reference_plan,
            "temporal_start_policy": continuity["temporal_start_policy"],
            "resolved_render_contract": {
                "profile": compiled.profile,
                "timing": timing,
                "generation": generation,
                "output": output,
            },
            "timing": timing,
            "generation": generation,
            "prompts": {
                "positive": compiled.positive_prompt,
                "negative": compiled.negative_prompt,
            },
            "output": output,
            "continuity_contract": continuity,
            "validation_contract": {
                "reject_if": [
                    "Canonical asset identity is not preserved.",
                    "Canonical geometry, scale, materials, markings or wardrobe are redesigned.",
                    "Required canonical references are substituted, merged or ignored.",
                    "An unrequested subject or object becomes a primary visual element.",
                    "Camera or lighting contradicts approved production authority.",
                ]
            },
            "composition_plan": composition_plan,
        }

    def _resolved_visual_assets(self, compiled: CompiledProductionPackage) -> list[dict[str, Any]]:
        raw_assets = compiled.production_authority.get("assets", [])
        assets = raw_assets if isinstance(raw_assets, list) else []
        resolved: list[dict[str, Any]] = []
        for raw in assets:
            if not isinstance(raw, dict):
                continue
            asset_id = str(raw.get("asset_id", "")).strip()
            category = str(raw.get("category", "")).strip().lower()
            reference = self._primary_reference(raw)
            item: dict[str, Any] = {
                "asset_id": asset_id,
                "category": category,
                "role": str(raw.get("role", "")).strip(),
                "requirement": str(raw.get("requirement", "")).strip(),
                "project_relative_path": reference or "",
            }
            if reference and self._looks_like_path(reference):
                resolved_path = self._resolve_project_path(reference)
                if not resolved_path.is_file():
                    raise ProviderReadyPackageResolutionError(
                        f"Canonical reference does not exist for {asset_id or 'asset'}: "
                        f"{resolved_path}"
                    )
                expected_checksum = self._reference_checksum(raw, reference)
                actual_checksum = self._sha256(resolved_path)
                if expected_checksum and actual_checksum.casefold() != expected_checksum.casefold():
                    raise ProviderReadyPackageResolutionError(
                        f"Canonical reference checksum mismatch for {asset_id}: {resolved_path}"
                    )
                item["resolved_source_path"] = str(resolved_path)
                item["checksum"] = actual_checksum
                item["provider_access"] = "local_absolute_path"
            else:
                item["resolved_source_path"] = ""
                item["checksum"] = ""
                item["provider_access"] = "metadata_only"
            resolved.append(item)
        return resolved

    def _reference_plan(
        self,
        resolved_visual_assets: list[dict[str, Any]],
        compiled: CompiledProductionPackage,
    ) -> dict[str, Any]:
        identity_references: list[dict[str, Any]] = []
        metadata_assets: list[dict[str, Any]] = []
        for item in resolved_visual_assets:
            asset_id = str(item.get("asset_id", ""))
            category = str(item.get("category", "")).lower()
            resolved_path = str(item.get("resolved_source_path", ""))
            if category in self.IDENTITY_CATEGORIES and resolved_path:
                identity_references.append(
                    {
                        "role": "primary_identity",
                        "asset_id": asset_id,
                        "category": category,
                        "image": resolved_path,
                        "delivery": "ic_lora",
                        "weight": 1.0,
                    }
                )
            else:
                metadata_assets.append(
                    {
                        "asset_id": asset_id,
                        "category": category,
                        "image": resolved_path,
                        "delivery": "prompt_metadata",
                    }
                )
        maximum = max(1, len(identity_references)) if identity_references else 1
        return {
            "schema_version": "1.0",
            "mode": "identity_first_minimal",
            "identity_references": identity_references,
            "metadata_assets": metadata_assets,
            "continuity": self._continuity_contract(compiled),
            "cinematography": {
                "camera": "prompt_metadata",
                "lighting": "prompt_metadata",
                "environment": "prompt_metadata",
                "effects": "prompt_metadata",
            },
            "ic_lora": {
                "enabled": bool(identity_references),
                "strength": compiled.ic_lora_strength,
                "maximum_identity_references": maximum,
            },
            "do_not_merge_assets": True,
            "reference_sheet_is_composition": False,
        }

    def _continuity_contract(self, compiled: CompiledProductionPackage) -> dict[str, Any]:
        start_frame = compiled.previous_approved_final_frame or ""
        resolved_start = ""
        if start_frame and self._looks_like_path(start_frame):
            path = self._resolve_project_path(start_frame)
            if not path.is_file():
                raise ProviderReadyPackageResolutionError(
                    f"Approved continuity frame does not exist: {path}"
                )
            resolved_start = str(path)
        has_start = bool(resolved_start)
        policy = {
            "schema_version": "1.0",
            "mode": "explicit_start_frame" if has_start else "empty_latent",
            "has_explicit_start_frame": has_start,
            "allowed_sources": [
                "explicit_start_frame",
                "previous_clip_end_frame",
                "approved_composition_frame",
            ],
            "fallback": "empty_latent",
            "allow_identity_reference": False,
            "allow_environment_reference": False,
            "allow_planet_reference": False,
            "allow_metadata_asset": False,
            "allow_first_resolved_asset": False,
        }
        return {
            "start_frame": resolved_start,
            "start_frame_source": "approved_continuity" if has_start else "NONE",
            "delivery": "start_frame" if has_start else "empty_latent",
            "included_in_ic_lora": False,
            "temporal_start_policy": policy,
        }

    def _resolved_profiles(self, compiled: CompiledProductionPackage) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        for category in ("camera", "lighting", "environment"):
            raw = compiled.production_authority.get(category)
            if not isinstance(raw, dict) or not raw:
                continue
            profiles.append(
                {
                    "category": category,
                    "profile_id": str(
                        raw.get(f"{category}_profile_asset_id", raw.get("profile", ""))
                    ),
                    "prompt_instructions": self._profile_instruction(category, raw),
                    "technical": deepcopy(raw),
                    "source": "approved-production-authority",
                }
            )
        return profiles

    @staticmethod
    def _profile_instruction(category: str, raw: dict[str, Any]) -> str:
        readable = [
            f"{str(key).replace('_', ' ')}: {value}"
            for key, value in raw.items()
            if value not in (None, "", [], {})
            and key not in {"provider_neutral", "continuity_notes"}
        ]
        return f"{category.title()} authority — " + "; ".join(readable)

    def _resolve_project_path(self, value: str) -> Path:
        normalized = value.strip()
        candidate = Path(normalized).expanduser()
        if candidate.is_absolute():
            return candidate.resolve(strict=False)
        if PureWindowsPath(normalized).is_absolute():
            return candidate
        return (self.project_directory / candidate).resolve(strict=False)

    @staticmethod
    def _primary_reference(asset: dict[str, Any]) -> str | None:
        direct = asset.get("canonical_reference")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        references = asset.get("canonical_references")
        if not isinstance(references, list):
            return None
        for raw in references:
            if not isinstance(raw, dict):
                continue
            value = raw.get("file_path")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _reference_checksum(asset: dict[str, Any], reference: str) -> str | None:
        references = asset.get("canonical_references")
        if not isinstance(references, list):
            return None
        normalized = reference.replace("/", "\\").casefold()
        for raw in references:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("file_path", "")).replace("/", "\\").casefold()
            if path != normalized:
                continue
            checksum = str(raw.get("checksum", "")).strip()
            return checksum or None
        return None

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        path = PureWindowsPath(value)
        return bool(path.suffix) or "/" in value or "\\" in value

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
