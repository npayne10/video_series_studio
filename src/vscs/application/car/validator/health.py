"""Repository health scoring extension point."""


class HealthScoringMixin:
    def calculate_health(self) -> float:
        """Compute repository health score in Phase 12.1.1 Part 5."""
        raise NotImplementedError("Implemented in Phase 12.1.1 Part 5.")
