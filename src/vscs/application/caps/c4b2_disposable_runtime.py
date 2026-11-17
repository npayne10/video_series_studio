"""C4B.2A: sealed disposable masked-Qwen staging and launch PREVIEW.

This module cannot start ComfyUI, perform HTTP requests, reserve an attempt,
register a Candidate or authorize GPU inference. Real C4B.2 execution is a
separately consented work item. Never use protected Candidate 4 here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.c4b_isolated_mask_provider import (
    inspect_c4b_node_schemas,
    prepare_c4b_isolated_blueprint,
    validate_c4b_api_graph,
)
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.application.caps.qwen_mask_aware_qualification import confirm_preserved_pixels
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_MARKER = ".c4b2_disposable_project"
_MARKER_TEXT = "C4B2_DISPOSABLE_PROJECT\n"
_MANIFEST = "c4b2_manifest.json"
_GRAPH = "c4b2_api_graph.json"
_MAX_PNG_BYTES = 40 * 1024 * 1024
_PROTECTED_ASSETS = frozenset({"STORY-PRO-B00D168E43"})


class C4B2IsolationError(RuntimeError):
    """A proposed disposable preflight violates the isolation contract."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _seal(payload: dict[str, Any]) -> str:
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _safe_path(path: Path, *, existing: bool) -> Path:
    if not path.is_absolute():
        raise C4B2IsolationError("Every C4B.2 path must be absolute")
    if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)):
        raise C4B2IsolationError("C4B.2 paths cannot contain symlinks or junction links")
    try:
        return path.resolve(strict=existing)
    except OSError as exc:
        raise C4B2IsolationError("C4B.2 path cannot be resolved") from exc


def _separate(a: Path, b: Path) -> bool:
    return a != b and a not in b.parents and b not in a.parents


def _roots(
    *, protected_project: Path, disposable_project: Path, bundle: Path
) -> tuple[Path, Path, Path]:
    protected = _safe_path(protected_project, existing=True)
    disposable = _safe_path(disposable_project, existing=True)
    target = _safe_path(bundle, existing=False)
    if not protected.is_dir() or not disposable.is_dir():
        raise C4B2IsolationError("Both project roots must already exist")
    if not all(
        _separate(a, b)
        for a, b in (
            (protected, disposable),
            (protected, target),
            (disposable, target),
        )
    ):
        raise C4B2IsolationError("C4B.2 workspace and both projects must be disjoint")
    marker = disposable / _MARKER
    if marker.is_symlink() or not marker.is_file():
        raise C4B2IsolationError("Disposable project must have a reviewed C4B.2 marker")
    if marker.read_text(encoding="utf-8") != _MARKER_TEXT:
        raise C4B2IsolationError("Disposable project marker is invalid")
    return protected, disposable, target


def _regular_png(path: Path) -> bytes:
    resolved = _safe_path(path, existing=True)
    if resolved.suffix.lower() != ".png" or not resolved.is_file():
        raise C4B2IsolationError("C4B.2 requires an ordinary PNG file")
    if resolved.stat().st_size > _MAX_PNG_BYTES:
        raise C4B2IsolationError("C4B.2 PNG exceeds the inspection byte limit")
    return resolved.read_bytes()


def _check_source_mask(source: bytes, mask: bytes) -> tuple[int, int]:
    from io import BytesIO

    try:
        with Image.open(BytesIO(source)) as image, Image.open(BytesIO(mask)) as roi:
            if (
                image.format != "PNG"
                or roi.format != "PNG"
                or image.mode != "RGB"
                or roi.mode != "L"
                or image.size != roi.size
                or image.width < 256
                or image.height < 256
                or image.width * image.height > 32_000_000
            ):
                raise C4B2IsolationError("C4B.2 requires equal-sized RGB source and L mask")
            histogram = roi.histogram()
            if any(histogram[1:255]) or histogram[0] == 0 or histogram[255] == 0:
                raise C4B2IsolationError("C4B.2 mask must have both binary regions")
            return image.size
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise C4B2IsolationError("C4B.2 PNG cannot be inspected") from exc


@dataclass(frozen=True, slots=True)
class C4B2DisposableBundle:
    """Prepared evidence; not a GPU job or execution consent."""

    directory: Path
    source_sha256: str
    mask_sha256: str
    graph_sha256: str
    manifest_sha256: str
    dimensions: tuple[int, int]
    dedicated_port: int = 8298

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def attempt_reservation_allowed(self) -> bool:
        return False

    @property
    def candidate_registration_allowed(self) -> bool:
        return False


def _json_file(path: Path) -> dict[str, Any]:
    raw = _regular_file(path)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise C4B2IsolationError("C4B.2 evidence JSON is invalid") from exc
    if not isinstance(value, dict):
        raise C4B2IsolationError("C4B.2 evidence must be a JSON object")
    return value


def _regular_file(path: Path) -> bytes:
    resolved = _safe_path(path, existing=True)
    if not resolved.is_file() or resolved.stat().st_size > 2_000_000:
        raise C4B2IsolationError("C4B.2 evidence is missing or oversized")
    return resolved.read_bytes()


def prepare_c4b2_disposable_bundle(
    snapshot: CandidateQualitySnapshot,
    proposal: GovernedCorrectionProposal,
    *,
    selected_mask_path: Path,
    protected_project_root: Path,
    bundle_directory: Path,
    seed: int = 1729,
) -> C4B2DisposableBundle:
    """Stage a single reviewed disposable source/mask; NEVER launch or POST."""
    if snapshot.asset_id in _PROTECTED_ASSETS:
        raise C4B2IsolationError("The protected Diagnostic Console is never a C4B.2 source")
    protected, disposable, target = _roots(
        protected_project=protected_project_root,
        disposable_project=snapshot.project_root,
        bundle=bundle_directory,
    )
    source_path = _safe_path(snapshot.image_path, existing=True)
    mask_path = _safe_path(selected_mask_path, existing=True)
    if disposable not in source_path.parents or disposable not in mask_path.parents:
        raise C4B2IsolationError("Both source and mask must belong to disposable project")
    if not target.parent.is_dir() or target.exists() or target.is_symlink():
        raise C4B2IsolationError("C4B.2 bundle parent must exist and target must be new")

    # Reuses complete C4A/C4B.1 current C1/C2, CAP and graph validation.
    blueprint = prepare_c4b_isolated_blueprint(
        snapshot, proposal, selected_mask_path=selected_mask_path, seed=seed
    )
    blueprint.verify_seal()
    source, mask = _regular_png(source_path), _regular_png(mask_path)
    if _sha(source) != blueprint.source_sha256 or _sha(mask) != blueprint.mask_sha256:
        raise C4B2IsolationError("C4B.2 staging source or mask changed")
    dimensions = _check_source_mask(source, mask)

    # All filesystem mutation is confined to a new, disjoint disposable root.
    target.mkdir(exist_ok=False)
    for name in ("input", "output", "temp", "user"):
        (target / name).mkdir(exist_ok=False)
    (target / "input" / blueprint.source_input_filename).write_bytes(source)
    (target / "input" / blueprint.mask_input_filename).write_bytes(mask)
    graph_bytes = json.dumps(blueprint.graph, sort_keys=True, indent=2).encode()
    (target / _GRAPH).write_bytes(graph_bytes)
    fields: dict[str, Any] = {
        "schema": "C4B2A_DISPOSABLE_OFFLINE_V1",
        "protected_project_root": str(protected),
        "disposable_project_root": str(disposable),
        "source_filename": blueprint.source_input_filename,
        "mask_filename": blueprint.mask_input_filename,
        "source_sha256": blueprint.source_sha256,
        "mask_sha256": blueprint.mask_sha256,
        "source_dimensions": list(dimensions),
        "graph_file_sha256": _sha(graph_bytes),
        "graph_sha256": blueprint.graph_sha256,
        "c4b1_evidence_sha256": blueprint.evidence_sha256,
        "c1_proposal_sha256": blueprint.c1_proposal_sha256,
        "managed_template_sha256": blueprint.managed_template_sha256,
        "seed": blueprint.seed,
        "dedicated_port": 8298,
        "output_prefix": blueprint.output_prefix,
        "execution_authorized": False,
        "input_staging_only": True,
        "attempt_reservation_allowed": False,
        "candidate_registration_allowed": False,
    }
    fields["manifest_seal"] = _seal(fields)
    (target / _MANIFEST).write_text(json.dumps(fields, indent=2, sort_keys=True), encoding="utf-8")
    return verify_c4b2_disposable_bundle(target)


def verify_c4b2_disposable_bundle(directory: Path) -> C4B2DisposableBundle:
    """Read-only recheck of isolation, source/mask bytes and graph provenance."""
    target = _safe_path(directory, existing=True)
    if not target.is_dir():
        raise C4B2IsolationError("C4B.2 bundle directory is missing")
    data = _json_file(target / _MANIFEST)
    seal = data.pop("manifest_seal", None)
    if not isinstance(seal, str) or seal != _seal(data):
        raise C4B2IsolationError("C4B.2 manifest integrity seal mismatch")
    if (
        data.get("schema") != "C4B2A_DISPOSABLE_OFFLINE_V1"
        or data.get("execution_authorized") is not False
        or data.get("input_staging_only") is not True
        or data.get("attempt_reservation_allowed") is not False
        or data.get("candidate_registration_allowed") is not False
        or data.get("dedicated_port") != 8298
    ):
        raise C4B2IsolationError("C4B.2 manifest grants unsupported execution authority")
    protected, disposable, checked = _roots(
        protected_project=Path(str(data["protected_project_root"])),
        disposable_project=Path(str(data["disposable_project_root"])),
        bundle=target,
    )
    if checked != target or not _separate(protected, checked) or not _separate(disposable, checked):
        raise C4B2IsolationError("C4B.2 bundle isolation changed")
    for folder in ("input", "output", "temp", "user"):
        path = _safe_path(target / folder, existing=True)
        if not path.is_dir() or path.parent != target:
            raise C4B2IsolationError("C4B.2 dedicated directory is missing")
    source_name, mask_name = data.get("source_filename"), data.get("mask_filename")
    if not isinstance(source_name, str) or not isinstance(mask_name, str):
        raise C4B2IsolationError("C4B.2 staged input name is unsafe")
    if not all(
        name.startswith("c4b_")
        and name.endswith(".png")
        and "/" not in name
        and "\\" not in name
        for name in (source_name, mask_name)
    ):
        raise C4B2IsolationError("C4B.2 staged input name is unsafe")
    source = _regular_png(target / "input" / source_name)
    mask = _regular_png(target / "input" / mask_name)
    dimensions = _check_source_mask(source, mask)
    if (
        _sha(source) != data.get("source_sha256")
        or _sha(mask) != data.get("mask_sha256")
        or list(dimensions) != data.get("source_dimensions")
    ):
        raise C4B2IsolationError("C4B.2 staged image evidence changed")
    graph_raw = _regular_file(target / _GRAPH)
    if _sha(graph_raw) != data.get("graph_file_sha256"):
        raise C4B2IsolationError("C4B.2 stored graph file changed")
    graph = _json_file(target / _GRAPH)
    validate_c4b_api_graph(graph)
    if (
        _seal(graph) != data.get("graph_sha256")
        or graph["C4B_SOURCE"]["inputs"]["image"] != source_name
        or graph["C4B_MASK"]["inputs"]["image"] != mask_name
        or graph["170:169"]["inputs"]["seed"] != data.get("seed")
        or graph["9"]["inputs"]["filename_prefix"] != data.get("output_prefix")
        or _sha(default_workflow_path().read_bytes()) != data.get("managed_template_sha256")
    ):
        raise C4B2IsolationError("C4B.2 graph or managed model baseline changed")
    return C4B2DisposableBundle(
        directory=target,
        source_sha256=data["source_sha256"],
        mask_sha256=data["mask_sha256"],
        graph_sha256=data["graph_sha256"],
        manifest_sha256=seal,
        dimensions=dimensions,
    )


def preview_c4b2_isolated_launch(
    directory: Path, *, python_executable: Path, comfyui_main: Path, port: int = 8298
) -> tuple[str, ...]:
    """Construct, but NEVER execute, a dedicated localhost ComfyUI command."""
    bundle = verify_c4b2_disposable_bundle(directory)
    interpreter = _safe_path(python_executable, existing=True)
    main = _safe_path(comfyui_main, existing=True)
    if (
        not interpreter.is_file()
        or not main.is_file()
        or main.name != "main.py"
        or type(port) is not int
        or port != bundle.dedicated_port
        or port == 8188
    ):
        raise C4B2IsolationError("C4B.2 launch preview must use a dedicated process/port")
    return (
        str(interpreter),
        str(main),
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
        "--input-directory",
        str(bundle.directory / "input"),
        "--output-directory",
        str(bundle.directory / "output"),
        "--temp-directory",
        str(bundle.directory / "temp"),
        "--user-directory",
        str(bundle.directory / "user"),
        "--disable-auto-launch",
    )


@dataclass(frozen=True, slots=True)
class C4B2OfflinePixelAudit:
    """Pixel comparison of external evidence, not proof of an AI provider job."""

    source_sha256: str
    mask_sha256: str
    result_sha256: str
    protected_changed_pixels: int
    editable_changed_pixels: int

    @property
    def protected_pixels_identical(self) -> bool:
        return self.protected_changed_pixels == 0

    @property
    def provider_inference_verified(self) -> bool:
        return False

    @property
    def candidate_registration_allowed(self) -> bool:
        return False


def audit_c4b2_external_result(directory: Path, *, result_png: Path) -> C4B2OfflinePixelAudit:
    """Compare an EXISTING isolated result; never generate, register or approve."""
    bundle = verify_c4b2_disposable_bundle(directory)
    output = _safe_path(result_png, existing=True)
    outroot = _safe_path(bundle.directory / "output", existing=True)
    if outroot not in output.parents:
        raise C4B2IsolationError("C4B.2 result is not inside disposable output")
    manifest = _json_file(bundle.directory / _MANIFEST)
    source = bundle.directory / "input" / str(manifest["source_filename"])
    mask = bundle.directory / "input" / str(manifest["mask_filename"])
    try:
        result = confirm_preserved_pixels(source, output, mask)
    except (OSError, ValueError, RuntimeError) as exc:
        raise C4B2IsolationError("C4B.2 external pixel evidence cannot be verified") from exc
    with Image.open(source) as original, Image.open(output) as image, Image.open(mask) as edit:
        if image.format != "PNG" or image.mode != "RGB":
            raise C4B2IsolationError("C4B.2 compared result must be RGB PNG")
        before, after, bits = original.tobytes(), image.tobytes(), edit.tobytes()
    inside_changes = sum(
        before[index * 3 : index * 3 + 3] != after[index * 3 : index * 3 + 3]
        for index, bit in enumerate(bits)
        if bit == 255
    )
    return C4B2OfflinePixelAudit(
        source_sha256=result["source_sha256"],
        mask_sha256=result["mask_sha256"],
        result_sha256=result["composite_sha256"],
        protected_changed_pixels=result["protected_changed_pixels"],
        editable_changed_pixels=inside_changes,
    )


@dataclass(frozen=True, slots=True)
class C4B2ReadinessEvidence:
    """Static GET response interpretation; never a GPU authorization."""

    missing_requirements: tuple[str, ...]
    gpu_devices: tuple[str, ...]
    graph_sha256: str

    @property
    def schema_readiness(self) -> bool:
        return not self.missing_requirements

    @property
    def runtime_mask_qualified(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False


def inspect_c4b2_offline_runtime_schemas(
    directory: Path, *, object_info: dict[str, Any], system_stats: dict[str, Any]
) -> C4B2ReadinessEvidence:
    """Validate externally supplied GET /object_info and /system_stats only.

    No HTTP call occurs. Installed node names alone are insufficient:
    ensure model filenames, key dropdown options, and mask-chain output
    port types match the compiled graph.
    """
    bundle = verify_c4b2_disposable_bundle(directory)
    graph = _json_file(bundle.directory / _GRAPH)
    problems = list(inspect_c4b_node_schemas(graph, object_info))
    for class_type, field, value in (
        ("UNETLoader", "unet_name", graph["170:161"]["inputs"]["unet_name"]),
        ("CLIPLoader", "clip_name", graph["170:162"]["inputs"]["clip_name"]),
        ("VAELoader", "vae_name", graph["170:146"]["inputs"]["vae_name"]),
        ("ImageScale", "upscale_method", "nearest-exact"),
        ("ImageScale", "upscale_method", "lanczos"),
        ("LoadImageMask", "channel", "red"),
    ):
        node = object_info.get(class_type)
        declared = node.get("input", {}) if isinstance(node, dict) else {}
        choice = None
        if isinstance(declared, dict):
            for group in ("required", "optional"):
                options = declared.get(group)
                if isinstance(options, dict) and field in options:
                    choice = options[field]
                    break
        choices = choice[0] if isinstance(choice, list) and choice else None
        if not isinstance(choices, list) or value not in choices:
            problems.append(f"{class_type}.{field} does not advertise {value}")
    for class_type, types in (
        ("LoadImage", ("IMAGE",)),
        ("LoadImageMask", ("MASK",)),
        ("GetImageSize", ("INT", "INT")),
        ("MaskToImage", ("IMAGE",)),
        ("ImageScale", ("IMAGE",)),
        ("ImageToMask", ("MASK",)),
        ("SetLatentNoiseMask", ("LATENT",)),
        ("ImageCompositeMasked", ("IMAGE",)),
    ):
        info = object_info.get(class_type)
        outputs = info.get("output") if isinstance(info, dict) else None
        if not isinstance(outputs, list) or tuple(outputs[: len(types)]) != types:
            problems.append(f"{class_type} output types are not the reviewed {types}")
    devices = []
    rows = system_stats.get("devices") if isinstance(system_stats, dict) else None
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("name"), str):
                total = row.get("vram_total")
                free = row.get("vram_free")
                if (
                    isinstance(total, (int, float))
                    and not isinstance(total, bool)
                    and total > 0
                    and isinstance(free, (int, float))
                    and not isinstance(free, bool)
                    and free >= 0
                    and free <= total
                ):
                    devices.append(
                        f"{row['name']}: {total / (1024**3):.1f} GiB total, "
                        f"{free / (1024**3):.1f} GiB free"
                    )
    if not devices:
        problems.append("No coherent total/free GPU memory inventory")
    # Model weights and peak VRAM are not inferred from this inventory.
    return C4B2ReadinessEvidence(
        missing_requirements=tuple(dict.fromkeys(problems)),
        gpu_devices=tuple(devices),
        graph_sha256=bundle.graph_sha256,
    )
