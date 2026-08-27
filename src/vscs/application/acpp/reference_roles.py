"""Provider-ready reference roles, validation, resolution, and provider binding."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import isclose
from typing import Mapping, Protocol


class ReferenceRole(StrEnum):
    """Governed role fulfilled by one shot-resolved visual reference."""

    SCENE_COMPOSITION_ANCHOR = "scene_composition_anchor"
    CONTINUITY_ANCHOR = "continuity_anchor"
    PRIMARY_IDENTITY = "primary_identity"
    SECONDARY_IDENTITY = "secondary_identity"
    GROUP_IDENTITY = "group_identity"
    ENVIRONMENT_REFERENCE = "environment_reference"
    BACKGROUND_IDENTITY = "background_identity"
    PROP_REFERENCE = "prop_reference"
    FURNITURE_REFERENCE = "furniture_reference"
    START_FRAME_REFERENCE = "start_frame_reference"
    END_FRAME_REFERENCE = "end_frame_reference"
    MOTION_REFERENCE = "motion_reference"
    STYLE_REFERENCE = "style_reference"


class ReferenceClass(StrEnum):
    """Governed origin class of a reference."""

    CANONICAL_MASTER = "canonical_master"
    PROVIDER_READY_DERIVATIVE = "provider_ready_derivative"
    SHOT_COMPOSITE = "shot_composite"
    CONTINUITY_CAPTURE = "continuity_capture"
    PROVIDER_SPECIFIC_HELPER = "provider_specific_helper"


class ReferencePriority(StrEnum):
    """Execution consequence when a reference is missing or unsuitable."""

    REQUIRED = "required"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class ReferenceSubjectType(StrEnum):
    """Broad subject class represented by a reference."""

    CHARACTER = "character"
    MULTI_SUBJECT_SCENE = "multi_subject_scene"
    ENVIRONMENT = "environment"
    PROP = "prop"
    FURNITURE = "furniture"
    VEHICLE = "vehicle"
    SHIP = "ship"
    EFFECT = "effect"
    OTHER = "other"


class CropRisk(StrEnum):
    """Estimated risk that provider preprocessing will hide required content."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Frame-state references are provider inputs whose pixel canvas defines the shot itself.
# They must match the requested video frame exactly. Supporting identity/environment
# references may retain provider-approved same-aspect dimensions.
_EXACT_TARGET_DIMENSION_ROLES = frozenset(
    {
        ReferenceRole.SCENE_COMPOSITION_ANCHOR,
        ReferenceRole.CONTINUITY_ANCHOR,
        ReferenceRole.START_FRAME_REFERENCE,
        ReferenceRole.END_FRAME_REFERENCE,
    }
)


@dataclass(frozen=True, slots=True)
class ReferenceCoverage:
    """Visibility and framing facts required to judge provider readiness."""

    framing_type: str
    coverage: str
    required_features_visible: bool = True
    identity_visible: bool = True
    full_required_asset_visible: bool = True


@dataclass(frozen=True, slots=True)
class ShotReference:
    """One governed reference bound to a shot role."""

    reference_id: str
    role: ReferenceRole
    reference_class: ReferenceClass
    priority: ReferencePriority
    subject_type: ReferenceSubjectType
    source_path: str
    canonical_source_id: str | None = None
    asset_id: str | None = None
    label: str = ""
    width: int = 0
    height: int = 0
    provider_ready: bool = False
    provider_profiles: tuple[str, ...] = ()
    coverage: ReferenceCoverage = field(
        default_factory=lambda: ReferenceCoverage(framing_type="unknown", coverage="unknown")
    )
    reference_fingerprint: str | None = None
    file_checksum: str | None = None
    contains_subjects: tuple[str, ...] = ()
    contains_props: tuple[str, ...] = ()
    contains_environments: tuple[str, ...] = ()

    @property
    def aspect_ratio(self) -> float | None:
        """Return numeric aspect ratio when dimensions are known."""
        if self.width <= 0 or self.height <= 0:
            return None
        return self.width / self.height


@dataclass(frozen=True, slots=True)
class ReferenceTarget:
    """Provider-neutral target profile used for reference suitability checks."""

    width: int
    height: int
    profile_id: str
    provider_id: str | None = None
    aspect_tolerance: float = 0.03

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


@dataclass(frozen=True, slots=True)
class ReferencePlan:
    """Resolved multi-reference plan for one production shot."""

    target: ReferenceTarget
    references: tuple[ShotReference, ...]
    schema_version: str = "1.0"

    def by_role(self, role: ReferenceRole) -> tuple[ShotReference, ...]:
        return tuple(reference for reference in self.references if reference.role is role)


class ReferenceResolutionSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ReferenceResolutionDiagnostic:
    severity: ReferenceResolutionSeverity
    code: str
    message: str
    reference_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderReferenceCapabilities:
    """Provider-edge declaration of directly bindable reference roles."""

    provider_id: str
    workflow_profile: str
    supported_roles: frozenset[ReferenceRole]
    maximum_references: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderReferenceBinding:
    """Provider-edge mapping from governed references into workflow inputs."""

    provider_id: str
    workflow_profile: str
    bindings: Mapping[str, tuple[str, ...]]
    fallback_strategy: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceResolutionResult:
    plan: ReferencePlan
    diagnostics: tuple[ReferenceResolutionDiagnostic, ...]
    provider_binding: ProviderReferenceBinding | None = None

    @property
    def passed(self) -> bool:
        return not any(
            diagnostic.severity is ReferenceResolutionSeverity.ERROR
            for diagnostic in self.diagnostics
        )


class ReferenceCatalog(Protocol):
    """Look up candidate shot references for one canonical asset."""

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        ...


@dataclass(frozen=True, slots=True)
class ReferenceRoleRequest:
    """Requested role that must be resolved for one asset or shot composite."""

    role: ReferenceRole
    priority: ReferencePriority
    asset_id: str | None = None
    preferred_reference_id: str | None = None


class ProviderReadyReferenceResolver:
    """Resolve role requests to suitable references and provider bindings."""

    def __init__(self, catalog: ReferenceCatalog) -> None:
        self.catalog = catalog

    def resolve(
        self,
        *,
        target: ReferenceTarget,
        requests: tuple[ReferenceRoleRequest, ...],
        supplied_references: tuple[ShotReference, ...] = (),
        capabilities: ProviderReferenceCapabilities | None = None,
    ) -> ReferenceResolutionResult:
        diagnostics: list[ReferenceResolutionDiagnostic] = []
        selected: list[ShotReference] = []
        supplied_by_id = {reference.reference_id: reference for reference in supplied_references}

        for request in requests:
            candidates = self._candidates(request, supplied_by_id)
            reference = self._select_best(candidates, target)
            if reference is None:
                diagnostics.append(
                    self._diagnostic(
                        request.priority,
                        "REFERENCE_ROLE_UNRESOLVED",
                        f"No reference could be resolved for role '{request.role.value}'.",
                        request.preferred_reference_id,
                    )
                )
                continue

            # Priority is a shot-level governance decision. A reusable catalog record may
            # have a softer default, but the active role request is authoritative for the
            # resolved shot plan and provider-binding consequences.
            reference = replace(reference, priority=request.priority)
            selected.append(reference)
            diagnostics.extend(self._validate_reference(reference, target, request.priority))

        selected = list(dict.fromkeys(selected))
        plan = ReferencePlan(target=target, references=tuple(selected))
        binding = None
        if capabilities is not None:
            binding, provider_diagnostics = self._bind_provider(plan, capabilities)
            diagnostics.extend(provider_diagnostics)
        return ReferenceResolutionResult(
            plan=plan,
            diagnostics=tuple(diagnostics),
            provider_binding=binding,
        )

    def _candidates(
        self,
        request: ReferenceRoleRequest,
        supplied_by_id: Mapping[str, ShotReference],
    ) -> tuple[ShotReference, ...]:
        if request.preferred_reference_id:
            preferred = supplied_by_id.get(request.preferred_reference_id)
            if preferred is None or preferred.role is not request.role:
                return ()
            return (preferred,)
        if request.asset_id is None:
            return tuple(
                reference
                for reference in supplied_by_id.values()
                if reference.role is request.role
            )
        return tuple(
            reference
            for reference in self.catalog.references_for_asset(request.asset_id)
            if reference.role is request.role
        )

    @staticmethod
    def _select_best(
        candidates: tuple[ShotReference, ...], target: ReferenceTarget
    ) -> ShotReference | None:
        if not candidates:
            return None

        def score(reference: ShotReference) -> tuple[int, int, int, int, int, int]:
            aspect_ok = ProviderReadyReferenceResolver._aspect_matches(reference, target)
            exact_dimensions = ProviderReadyReferenceResolver._dimensions_match(reference, target)
            profile_ok = not reference.provider_profiles or target.profile_id in reference.provider_profiles
            complete = reference.coverage.full_required_asset_visible
            identity_visible = reference.coverage.identity_visible
            return (
                int(reference.provider_ready),
                int(exact_dimensions),
                int(aspect_ok),
                int(profile_ok),
                int(complete),
                int(identity_visible),
            )

        return max(candidates, key=score)

    @staticmethod
    def _aspect_matches(reference: ShotReference, target: ReferenceTarget) -> bool:
        aspect = reference.aspect_ratio
        if aspect is None:
            return False
        return isclose(aspect, target.aspect_ratio, rel_tol=target.aspect_tolerance)

    @staticmethod
    def _dimensions_match(reference: ShotReference, target: ReferenceTarget) -> bool:
        return reference.width == target.width and reference.height == target.height

    def _validate_reference(
        self,
        reference: ShotReference,
        target: ReferenceTarget,
        priority: ReferencePriority,
    ) -> tuple[ReferenceResolutionDiagnostic, ...]:
        findings: list[ReferenceResolutionDiagnostic] = []
        if not reference.provider_ready:
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_NOT_PROVIDER_READY",
                    f"Reference '{reference.reference_id}' is not approved as provider-ready.",
                    reference.reference_id,
                )
            )
        if not self._aspect_matches(reference, target):
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_ASPECT_MISMATCH",
                    f"Reference '{reference.reference_id}' aspect ratio is incompatible with "
                    f"target {target.width}x{target.height}.",
                    reference.reference_id,
                )
            )
        if reference.width <= 0 or reference.height <= 0:
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_DIMENSIONS_UNKNOWN",
                    f"Reference '{reference.reference_id}' has no usable dimensions.",
                    reference.reference_id,
                )
            )
        elif (
            reference.role in _EXACT_TARGET_DIMENSION_ROLES
            and not self._dimensions_match(reference, target)
        ):
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_DIMENSIONS_MISMATCH",
                    f"Frame anchor '{reference.reference_id}' must match target dimensions "
                    f"exactly ({target.width}x{target.height}); got "
                    f"{reference.width}x{reference.height}.",
                    reference.reference_id,
                )
            )
        if not reference.coverage.required_features_visible:
            findings.append(
                self._diagnostic(
                    priority,
                    "REQUIRED_FEATURES_NOT_VISIBLE",
                    f"Reference '{reference.reference_id}' does not show all required features.",
                    reference.reference_id,
                )
            )
        if not reference.coverage.full_required_asset_visible:
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_EXTRAPOLATION_RISK",
                    f"Reference '{reference.reference_id}' would require provider extrapolation "
                    "for required asset content.",
                    reference.reference_id,
                )
            )
        if reference.role in {
            ReferenceRole.PRIMARY_IDENTITY,
            ReferenceRole.SECONDARY_IDENTITY,
            ReferenceRole.GROUP_IDENTITY,
        } and not reference.coverage.identity_visible:
            findings.append(
                self._diagnostic(
                    priority,
                    "IDENTITY_NOT_VISIBLE",
                    f"Reference '{reference.reference_id}' does not expose identity-critical detail.",
                    reference.reference_id,
                )
            )
        if reference.provider_profiles and target.profile_id not in reference.provider_profiles:
            findings.append(
                self._diagnostic(
                    priority,
                    "REFERENCE_PROFILE_UNSUPPORTED",
                    f"Reference '{reference.reference_id}' is not approved for profile "
                    f"'{target.profile_id}'.",
                    reference.reference_id,
                )
            )
        return tuple(findings)

    def _bind_provider(
        self,
        plan: ReferencePlan,
        capabilities: ProviderReferenceCapabilities,
    ) -> tuple[ProviderReferenceBinding, tuple[ReferenceResolutionDiagnostic, ...]]:
        diagnostics: list[ReferenceResolutionDiagnostic] = []
        direct: dict[str, list[str]] = {}
        unsupported_required: list[ShotReference] = []
        for reference in plan.references:
            if reference.role in capabilities.supported_roles:
                direct.setdefault(reference.role.value, []).append(reference.reference_id)
            elif reference.priority is ReferencePriority.REQUIRED:
                unsupported_required.append(reference)

        if capabilities.maximum_references is not None:
            direct_count = sum(len(values) for values in direct.values())
            if direct_count > capabilities.maximum_references:
                diagnostics.append(
                    ReferenceResolutionDiagnostic(
                        severity=ReferenceResolutionSeverity.ERROR,
                        code="PROVIDER_REFERENCE_LIMIT_EXCEEDED",
                        message=(
                            f"Provider '{capabilities.provider_id}' accepts at most "
                            f"{capabilities.maximum_references} references; {direct_count} were mapped."
                        ),
                    )
                )

        fallback = None
        if unsupported_required:
            composition = plan.by_role(ReferenceRole.SCENE_COMPOSITION_ANCHOR)
            if composition and ReferenceRole.SCENE_COMPOSITION_ANCHOR in capabilities.supported_roles:
                fallback = "scene_composition_anchor"
                diagnostics.append(
                    ReferenceResolutionDiagnostic(
                        severity=ReferenceResolutionSeverity.WARNING,
                        code="PROVIDER_REFERENCE_FALLBACK",
                        message=(
                            "Provider cannot bind all required roles directly; governed scene "
                            "composition fallback is required."
                        ),
                    )
                )
            else:
                diagnostics.append(
                    ReferenceResolutionDiagnostic(
                        severity=ReferenceResolutionSeverity.ERROR,
                        code="PROVIDER_REQUIRED_ROLE_UNSUPPORTED",
                        message=(
                            "Provider cannot consume required reference roles and no governed "
                            "composition fallback is available."
                        ),
                    )
                )

        binding = ProviderReferenceBinding(
            provider_id=capabilities.provider_id,
            workflow_profile=capabilities.workflow_profile,
            bindings={key: tuple(values) for key, values in direct.items()},
            fallback_strategy=fallback,
        )
        return binding, tuple(diagnostics)

    @staticmethod
    def _diagnostic(
        priority: ReferencePriority,
        code: str,
        message: str,
        reference_id: str | None,
    ) -> ReferenceResolutionDiagnostic:
        severity = (
            ReferenceResolutionSeverity.ERROR
            if priority is ReferencePriority.REQUIRED
            else ReferenceResolutionSeverity.WARNING
        )
        return ReferenceResolutionDiagnostic(
            severity=severity,
            code=code,
            message=message,
            reference_id=reference_id,
        )
