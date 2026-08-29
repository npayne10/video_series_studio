"""Compile governed shot references from real provider-ready image files."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from vscs.application.acpp.reference_roles import (
    ProviderReadyReferenceResolver,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceResolutionDiagnostic,
    ReferenceResolutionSeverity,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)


class GovernedReferenceCompilationError(RuntimeError):
    """Raised when a governed reference plan cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class GovernedReferenceCompilationResult:
    """Compiled provider-neutral plan plus operator-visible diagnostics."""

    plan: ReferencePlan
    diagnostics: tuple[ReferenceResolutionDiagnostic, ...]

    @property
    def passed(self) -> bool:
        return not any(
            diagnostic.severity is ReferenceResolutionSeverity.ERROR
            for diagnostic in self.diagnostics
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic JSON contract persisted by XPC."""
        return {
            "schema_version": self.plan.schema_version,
            "status": "passed" if self.passed else "failed",
            "target": {
                "width": self.plan.target.width,
                "height": self.plan.target.height,
                "profile_id": self.plan.target.profile_id,
                "provider_id": self.plan.target.provider_id,
                "aspect_tolerance": self.plan.target.aspect_tolerance,
            },
            "references": [_reference_to_dict(reference) for reference in self.plan.references],
            "diagnostics": [
                {
                    "severity": diagnostic.severity.value,
                    "code": diagnostic.code,
                    "message": diagnostic.message,
                    "reference_id": diagnostic.reference_id,
                }
                for diagnostic in self.diagnostics
            ],
        }


class _EmptyReferenceCatalog:
    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        del asset_id
        return ()


class GovernedReferenceCompiler:
    """Refresh file facts and validate an optional governed reference-plan payload."""

    def __init__(self, reference_root: Path | None = None) -> None:
        self.reference_root = (
            Path(reference_root).expanduser().resolve(strict=False)
            if reference_root is not None
            else None
        )
        self.resolver = ProviderReadyReferenceResolver(_EmptyReferenceCatalog())

    def compile(
        self,
        raw_plan: object,
        *,
        width: int,
        height: int,
        profile: str,
    ) -> GovernedReferenceCompilationResult | None:
        """Compile one raw governed plan; return ``None`` for legacy packages."""
        if raw_plan is None:
            return None
        if not isinstance(raw_plan, dict):
            raise GovernedReferenceCompilationError("reference_plan must be a JSON object")

        target_raw = raw_plan.get("target")
        if target_raw is not None and not isinstance(target_raw, dict):
            raise GovernedReferenceCompilationError("reference_plan.target must be a JSON object")
        target_data = dict(target_raw or {})
        declared_width = _positive_int(target_data.get("width"), width)
        declared_height = _positive_int(target_data.get("height"), height)
        if declared_width != width or declared_height != height:
            raise GovernedReferenceCompilationError(
                "REFERENCE_TARGET_MISMATCH: governed reference target "
                f"{declared_width}x{declared_height} does not match render target {width}x{height}"
            )

        profile_id = _text(target_data.get("profile_id")) or f"{profile}-video-16x9"
        provider_id = _text(target_data.get("provider_id"))
        aspect_tolerance = _positive_float(target_data.get("aspect_tolerance"), 0.03)
        target = ReferenceTarget(
            width=width,
            height=height,
            profile_id=profile_id,
            provider_id=provider_id,
            aspect_tolerance=aspect_tolerance,
        )

        references_raw = raw_plan.get("references")
        if not isinstance(references_raw, list) or not references_raw:
            raise GovernedReferenceCompilationError(
                "REFERENCE_PLAN_EMPTY: governed reference_plan must contain references"
            )

        supplied = tuple(self._compile_reference(item) for item in references_raw)
        ids = [reference.reference_id for reference in supplied]
        if len(set(ids)) != len(ids):
            raise GovernedReferenceCompilationError(
                "REFERENCE_PLAN_DUPLICATE_ID: governed reference IDs must be unique"
            )

        requests = tuple(
            ReferenceRoleRequest(
                role=reference.role,
                priority=reference.priority,
                asset_id=reference.asset_id,
                preferred_reference_id=reference.reference_id,
            )
            for reference in supplied
        )
        resolution = self.resolver.resolve(
            target=target,
            requests=requests,
            supplied_references=supplied,
        )
        result = GovernedReferenceCompilationResult(
            plan=replace(
                resolution.plan,
                schema_version=_text(raw_plan.get("schema_version")) or "1.0",
            ),
            diagnostics=resolution.diagnostics,
        )
        if not result.passed:
            errors = [
                f"{item.code}: {item.message}"
                for item in result.diagnostics
                if item.severity is ReferenceResolutionSeverity.ERROR
            ]
            raise GovernedReferenceCompilationError("; ".join(errors))
        return result

    def _compile_reference(self, raw: object) -> ShotReference:
        if not isinstance(raw, dict):
            raise GovernedReferenceCompilationError(
                "reference_plan.references entries must be JSON objects"
            )
        try:
            role = ReferenceRole(str(raw["role"]))
            reference_class = ReferenceClass(str(raw["reference_class"]))
            priority = ReferencePriority(str(raw["priority"]))
            subject_type = ReferenceSubjectType(str(raw["subject_type"]))
        except KeyError as exc:
            raise GovernedReferenceCompilationError(
                f"Governed reference is missing required field: {exc.args[0]}"
            ) from exc
        except ValueError as exc:
            raise GovernedReferenceCompilationError(
                f"Governed reference contains an unsupported enum value: {exc}"
            ) from exc

        reference_id = _required_text(raw, "reference_id")
        source_path = _required_text(raw, "source_path")
        disk_path = self._resolve_source_path(source_path, reference_id)
        width, height = _image_dimensions(disk_path)
        checksum = _sha256_file(disk_path)
        coverage_raw = raw.get("coverage")
        if coverage_raw is not None and not isinstance(coverage_raw, dict):
            raise GovernedReferenceCompilationError(
                f"Reference '{reference_id}' coverage must be a JSON object"
            )
        coverage_data = dict(coverage_raw or {})
        coverage = ReferenceCoverage(
            framing_type=_text(coverage_data.get("framing_type")) or "unknown",
            coverage=_text(coverage_data.get("coverage")) or "unknown",
            required_features_visible=_boolean(
                coverage_data.get("required_features_visible"), True
            ),
            identity_visible=_boolean(coverage_data.get("identity_visible"), True),
            full_required_asset_visible=_boolean(
                coverage_data.get("full_required_asset_visible"), True
            ),
        )
        provider_profiles_raw = raw.get("provider_profiles", [])
        if not isinstance(provider_profiles_raw, list | tuple):
            raise GovernedReferenceCompilationError(
                f"Reference '{reference_id}' provider_profiles must be a list"
            )
        provider_profiles = tuple(
            text for item in provider_profiles_raw if (text := _text(item)) is not None
        )
        reference = ShotReference(
            reference_id=reference_id,
            role=role,
            reference_class=reference_class,
            priority=priority,
            subject_type=subject_type,
            source_path=source_path,
            canonical_source_id=_text(raw.get("canonical_source_id")),
            asset_id=_text(raw.get("asset_id")),
            label=_text(raw.get("label")) or "",
            width=width,
            height=height,
            provider_ready=_boolean(raw.get("provider_ready"), False),
            provider_profiles=provider_profiles,
            coverage=coverage,
            file_checksum=checksum,
            contains_subjects=_text_tuple(raw.get("contains_subjects")),
            contains_props=_text_tuple(raw.get("contains_props")),
            contains_environments=_text_tuple(raw.get("contains_environments")),
        )
        fingerprint_payload = _reference_to_dict(reference)
        fingerprint_payload["reference_fingerprint"] = None
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return replace(reference, reference_fingerprint=fingerprint)

    def _resolve_source_path(self, source_path: str, reference_id: str) -> Path:
        candidate = Path(source_path).expanduser()
        if not candidate.is_absolute():
            if self.reference_root is None:
                raise GovernedReferenceCompilationError(
                    f"REFERENCE_FILE_ROOT_UNKNOWN: reference '{reference_id}' uses relative path "
                    f"'{source_path}' but XPC has no project reference root"
                )
            candidate = self.reference_root / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_file():
            raise GovernedReferenceCompilationError(
                f"REFERENCE_FILE_MISSING: reference '{reference_id}' file does not exist: {candidate}"
            )
        return candidate


def _reference_to_dict(reference: ShotReference) -> dict[str, Any]:
    data = asdict(reference)
    data["role"] = reference.role.value
    data["reference_class"] = reference.reference_class.value
    data["priority"] = reference.priority.value
    data["subject_type"] = reference.subject_type.value
    data["provider_profiles"] = list(reference.provider_profiles)
    data["contains_subjects"] = list(reference.contains_subjects)
    data["contains_props"] = list(reference.contains_props)
    data["contains_environments"] = list(reference.contains_environments)
    return data


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(32)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
            width, height = struct.unpack(">II", header[16:24])
            return _checked_dimensions(path, width, height)
        if header[:2] == b"\xff\xd8":
            stream.seek(2)
            while True:
                prefix = stream.read(1)
                if not prefix:
                    break
                if prefix != b"\xff":
                    continue
                marker = stream.read(1)
                while marker == b"\xff":
                    marker = stream.read(1)
                if not marker or marker in {b"\xd8", b"\xd9"}:
                    continue
                length_raw = stream.read(2)
                if len(length_raw) != 2:
                    break
                length = struct.unpack(">H", length_raw)[0]
                if length < 2:
                    break
                if marker[0] in {
                    0xC0,
                    0xC1,
                    0xC2,
                    0xC3,
                    0xC5,
                    0xC6,
                    0xC7,
                    0xC9,
                    0xCA,
                    0xCB,
                    0xCD,
                    0xCE,
                    0xCF,
                }:
                    payload = stream.read(length - 2)
                    if len(payload) < 5:
                        break
                    height, width = struct.unpack(">HH", payload[1:5])
                    return _checked_dimensions(path, width, height)
                stream.seek(length - 2, 1)
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            width, height = _webp_dimensions(header, path)
            return _checked_dimensions(path, width, height)
    raise GovernedReferenceCompilationError(
        f"REFERENCE_IMAGE_UNREADABLE: unsupported or corrupt image file: {path}"
    )


def _webp_dimensions(header: bytes, path: Path) -> tuple[int, int]:
    chunk = header[12:16]
    if chunk == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(header) >= 25 and header[20] == 0x2F:
        bits = int.from_bytes(header[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    raise GovernedReferenceCompilationError(
        f"REFERENCE_IMAGE_UNREADABLE: unsupported WEBP variant: {path}"
    )


def _checked_dimensions(path: Path, width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise GovernedReferenceCompilationError(
            f"REFERENCE_IMAGE_UNREADABLE: invalid image dimensions in {path}"
        )
    return width, height


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = _text(raw.get(key))
    if value is None:
        raise GovernedReferenceCompilationError(
            f"Governed reference is missing required field: {key}"
        )
    return value


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(text for item in value if (text := _text(item)) is not None)


def _boolean(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _positive_int(value: object, default: int) -> int:
    return (
        value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default
    )


def _positive_float(value: object, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
        return float(value)
    return default
