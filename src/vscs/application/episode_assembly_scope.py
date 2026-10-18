"""Fail-closed lookup of pre-existing governed Episode Assembly scope evidence."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assembly_contracts import AssemblyScope, AssemblyScopeKind
from vscs.infrastructure.shot_set_completion import JsonShotSetCompletionRepository


def verified_episode_assembly_scope(
    project_directory: Path | None, episode_id: str, expected_shot_ids: tuple[str, ...]
) -> AssemblyScope | None:
    """Reuse only a valid published Shot-set declaration, never invent a revision.

    A first-time partial Draft still requires a separate approved planning-snapshot
    scope authority; this lookup cannot provide one without existing evidence.
    """
    if project_directory is None or not episode_id.strip() or not expected_shot_ids:
        return None
    repository = JsonShotSetCompletionRepository(project_directory)
    if not repository.root.is_dir():
        return None
    matching: list[AssemblyScope] = []
    for path in sorted(repository.root.glob("*.json")):
        declaration = repository.get(path.stem)
        if declaration is None:
            raise ValueError("Declared Shot-set evidence disappeared during resolution")
        if (
            declaration.scope.scope_kind is AssemblyScopeKind.EPISODE
            and declaration.scope.scope_id == episode_id.strip().upper()
        ):
            if declaration.expected_shot_ids != expected_shot_ids:
                raise ValueError("Declared Episode Shot set differs from current planning")
            matching.append(declaration.scope)
    if not matching:
        return None
    if any(item != matching[0] for item in matching[1:]):
        raise ValueError("Conflicting governed Shot-set scope declarations")
    return matching[0]
