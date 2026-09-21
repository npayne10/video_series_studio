"""Register one explicitly approved VSCS Shot Composition Keyframe."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from vscs.application.production_execution import (
    KEYFRAME_ACCEPTANCE_CRITERIA,
    GovernedShotKeyframe,
    GovernedShotKeyframeStore,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()

    project = Path(args.project_dir).expanduser().resolve(strict=True)
    image = Path(args.image).expanduser().resolve(strict=True)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    try:
        stored_path = str(image.relative_to(project))
    except ValueError:
        stored_path = str(image)

    record = GovernedShotKeyframe(
        shot_id=args.shot_id.strip().upper(),
        image_path=stored_path,
        image_sha256=digest,
        approved_by=args.approved_by.strip(),
        approved_at=datetime.now(UTC).isoformat(),
        acceptance_criteria=KEYFRAME_ACCEPTANCE_CRITERIA,
    )
    saved = GovernedShotKeyframeStore(project).save(record)
    print(f"Registered governed keyframe for {saved.shot_id}")
    print(f"Image: {image}")
    print(f"SHA256: {saved.image_sha256}")


if __name__ == "__main__":
    main()
