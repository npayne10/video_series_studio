from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from vscs.application.production_execution import (
    CanonicalInjectionAsset,
    InjectionRegionAuthority,
    IntroductionInjectionMode,
    IntroductionInjectionRequest,
    IntroductionInjectionSide,
)
from vscs.infrastructure.production_execution import (
    ComfyUIIntroductionInjectionSynthesisError,
    ComfyUIIntroductionInjectionSynthesizer,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png(
    path: Path,
    value: tuple[int, int, int],
    *,
    size: tuple[int, int] = (1280, 720),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, value).save(path)
    return path


def _request(project: Path, *, seed: int = 138) -> IntroductionInjectionRequest:
    source = _png(project / "source" / "frame-000095.png", (10, 20, 30))
    ros = _png(project / "refs" / "ros.png", (100, 110, 120), size=(512, 768))
    asset = CanonicalInjectionAsset(
        asset_id="CAP-CHR-005",
        asset_kind="character",
        reference_ids=("REF-ROS",),
        reference_paths=(str(ros),),
        reference_sha256=(_sha(ros),),
    )
    region = InjectionRegionAuthority(
        side=IntroductionInjectionSide.RIGHT,
        left=0.82,
        top=0.08,
        right=1.0,
        bottom=0.96,
        partial_visibility_required=True,
        max_subject_scale_ratio=0.55,
    )
    return IntroductionInjectionRequest(
        shot_id="EP-001-SCN-001-SHT-002",
        requirement_id="GIKR-ROS-ENTER",
        boundary_id="GISB-ROS-ENTER",
        source_span_id="GIRS-SPAN-001",
        target_span_id="GIRS-SPAN-002",
        source_global_frame_index=95,
        target_global_frame_index=96,
        source_boundary_image_path=str(source),
        source_boundary_image_sha256=_sha(source),
        canonical_asset=asset,
        injection_region=region,
        width=1280,
        height=720,
        seed=seed,
        timed_asset_presence_fingerprint="TIMED-FP",
        source_package_fingerprint="PACKAGE-FP",
        mode=IntroductionInjectionMode.CHARACTER_ENTER,
    )


class _InjectionClient:
    def __init__(self, fill: tuple[int, int, int] = (220, 40, 50)) -> None:
        self.fill = fill
        self.prompt: dict[str, Any] | None = None
        self.runtime_payload: dict[str, Any] | None = None
        self.submit_calls = 0

    def healthcheck(self) -> None:
        return None

    def validate_nodes(self, prompt: dict[str, Any]) -> None:
        assert prompt["1"]["class_type"] == "VSCSIntroductionBoundaryPackageLoaderV1"

    def submit(self, prompt: dict[str, Any]) -> str:
        self.submit_calls += 1
        self.prompt = prompt
        request_file = Path(prompt["1"]["inputs"]["request_file"])
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        self.runtime_payload = payload
        output = Path(payload["output_directory"]) / payload["output_filename"]
        Image.new(
            "RGB",
            (int(payload["width"]), int(payload["height"])),
            self.fill,
        ).save(output)
        return "prompt-injection"

    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]:
        assert prompt_id == "prompt-injection"
        return {"status": {"completed": True}}


def test_synthesizer_edits_only_governed_region_and_preserves_scene_outside(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    client = _InjectionClient()
    synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=client,  # type: ignore[arg-type]
    )

    result = synthesizer.synthesize(request, attempt_number=1)

    candidate = Path(result.image_path)
    assert candidate.is_file()
    assert result.request_id == request.request_id
    assert result.canonical_asset_id == request.canonical_asset.authority_id
    assert result.injection_region_id == request.injection_region.region_id
    assert result.attempt_number == 1
    assert request.request_id in candidate.parts

    with Image.open(request.source_boundary_image_path) as source_image:
        source = source_image.convert("RGB")
        with Image.open(candidate) as candidate_image:
            output = candidate_image.convert("RGB")
            assert output.crop((0, 0, 1056, 720)).tobytes() == source.crop(
                (0, 0, 1056, 720)
            ).tobytes()
            assert output.crop((1056, 0, 1280, 64)).tobytes() == source.crop(
                (1056, 0, 1280, 64)
            ).tobytes()
            assert output.crop((1056, 688, 1280, 720)).tobytes() == source.crop(
                (1056, 688, 1280, 720)
            ).tobytes()
            assert output.getpixel((1270, 360)) == client.fill

    assert client.runtime_payload is not None
    runtime = client.runtime_payload
    assert runtime["canonical_asset_id"] == "CAP-CHR-005"
    assert runtime["introduced_reference_ids"] == ["REF-ROS"]
    assert runtime["injection_pixel_box"] == [1050, 58, 1280, 691]
    assert runtime["provider_edit_box"] == [1056, 64, 1280, 688]
    assert runtime["width"] == 224
    assert runtime["height"] == 624
    assert "first visible phase" in runtime["positive_prompt"]
    assert "RIGHT edge" in runtime["positive_prompt"]
    assert "Add no other person or asset" in runtime["positive_prompt"]
    assert "second entrant" in runtime["negative_prompt"]


def test_synthesizer_rejects_canonical_reference_checksum_drift(tmp_path: Path) -> None:
    request = _request(tmp_path)
    reference = Path(request.canonical_asset.reference_paths[0])
    reference.write_bytes(reference.read_bytes() + b"tampered")
    client = _InjectionClient()
    synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(
        ComfyUIIntroductionInjectionSynthesisError,
        match="canonical injection reference checksum changed",
    ):
        synthesizer.synthesize(request, attempt_number=1)

    assert client.submit_calls == 0


def test_synthesizer_rejects_source_boundary_checksum_drift(tmp_path: Path) -> None:
    request = _request(tmp_path)
    source = Path(request.source_boundary_image_path)
    source.write_bytes(source.read_bytes() + b"tampered")
    client = _InjectionClient()
    synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(
        ComfyUIIntroductionInjectionSynthesisError,
        match="Source boundary checksum changed",
    ):
        synthesizer.synthesize(request, attempt_number=1)

    assert client.submit_calls == 0


def test_retry_uses_new_request_scoped_directory_and_preserves_previous_candidate(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    first_synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=_InjectionClient((200, 10, 20)),  # type: ignore[arg-type]
    )
    first = first_synthesizer.synthesize(request, attempt_number=1)
    first_path = Path(first.image_path)
    first_sha = _sha(first_path)

    retry = replace(request, seed=request.seed + 1)
    second_synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=_InjectionClient((20, 200, 10)),  # type: ignore[arg-type]
    )
    second = second_synthesizer.synthesize(retry, attempt_number=2)

    assert retry.request_id != request.request_id
    assert second.image_path != first.image_path
    assert request.request_id in first_path.parts
    assert retry.request_id in Path(second.image_path).parts
    assert first_path.is_file()
    assert _sha(first_path) == first_sha


def test_same_request_cannot_overwrite_immutable_candidate(tmp_path: Path) -> None:
    request = _request(tmp_path)
    synthesizer = ComfyUIIntroductionInjectionSynthesizer(
        tmp_path,
        client=_InjectionClient(),  # type: ignore[arg-type]
    )
    synthesizer.synthesize(request, attempt_number=1)

    with pytest.raises(
        ComfyUIIntroductionInjectionSynthesisError,
        match="already contains a final candidate",
    ):
        synthesizer.synthesize(request, attempt_number=1)
