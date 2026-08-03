"""Small reporting model for VSCS functional certification results."""

from __future__ import annotations

from dataclasses import dataclass

from certification_matrix import ONBOARDING_FUNCTIONAL_MATRIX


@dataclass(frozen=True, slots=True)
class CertificationResult:
    """Pass or fail result for one certification area."""

    area: str
    passed: bool
    detail: str = ""


class CertificationRunner:
    """Collect certification results and produce a stable text report."""

    def __init__(self) -> None:
        self._results: dict[str, CertificationResult] = {}

    def record(self, area: str, *, passed: bool, detail: str = "") -> None:
        """Record the current result for a known functional area."""
        known_areas = {evidence.area for evidence in ONBOARDING_FUNCTIONAL_MATRIX}
        if area not in known_areas:
            raise ValueError(f"Unknown certification area: {area}")
        self._results[area] = CertificationResult(area, passed, detail)

    @property
    def complete(self) -> bool:
        """Return whether every matrix area has a recorded result."""
        return len(self._results) == len(ONBOARDING_FUNCTIONAL_MATRIX)

    @property
    def passed(self) -> bool:
        """Return whether certification is complete and every area passed."""
        return self.complete and all(result.passed for result in self._results.values())

    def report(self) -> str:
        """Return a human-readable certification report."""
        lines = [
            "VSCS Onboarding Functional Certification",
            "=" * 42,
        ]
        for evidence in ONBOARDING_FUNCTIONAL_MATRIX:
            result = self._results.get(evidence.area)
            status = "NOT RUN" if result is None else "PASS" if result.passed else "FAIL"
            lines.append(f"{evidence.area:.<32} {status}")
            if result is not None and result.detail:
                lines.append(f"  {result.detail}")
        lines.extend(
            (
                "-" * 42,
                f"OVERALL RESULT: {'PASS' if self.passed else 'FAIL'}",
            )
        )
        return "\n".join(lines)
