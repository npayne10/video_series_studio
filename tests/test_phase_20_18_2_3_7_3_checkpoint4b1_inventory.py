"""Checkpoint 4B.1: evidence inventory never equates media with timeline approval."""

from types import SimpleNamespace

from vscs.application.episode_evidence_inventory import reconcile_shot_evidence


def _media(shot, state):
    events = (
        (SimpleNamespace(to_state=SimpleNamespace(value="approved")),)
        if state == "approved" else ()
    )
    return SimpleNamespace(
        scope=SimpleNamespace(shot_id=shot),
        state=SimpleNamespace(value=state),
        governance_history=events,
    )


def test_media_exists_but_timeline_missing_and_qc_pending():
    rows = reconcile_shot_evidence(
        ("SHT-003",), (), (), (_media("SHT-003", "generated"),), ()
    )
    assert rows[0].media == "Exists — QC/approval pending"
    assert rows[0].assembly == "Not in timeline"
    assert "QC approval pending" in rows[0].blockers[-1]


def test_missing_media_is_distinct_from_missing_timeline():
    rows = reconcile_shot_evidence(("SHT-001",), (), (), (), ())
    assert rows[0].media == "No media record"
    assert rows[0].assembly == "Not in timeline"
    assert len(rows[0].blockers) == 2


def test_approved_media_without_timeline_does_not_imply_assembly():
    rows = reconcile_shot_evidence(
        ("SHT-002",), (), (), (_media("SHT-002", "approved"),), ()
    )
    assert rows[0].media == "1 approved / 1 records"
    assert rows[0].assembly == "Not in timeline"


def test_planning_and_task_evidence_are_separate():
    task = SimpleNamespace(
        shot_id="SHT-001", state=SimpleNamespace(value="completed")
    )
    rows = reconcile_shot_evidence(
        ("SHT-001",),
        ("SHT-001: Planning Review not current",),
        (),
        (),
        (task,),
    )
    assert rows[0].planning == "Blocked"
    assert rows[0].production_task == "completed"
    assert "Planning Review" in rows[0].blockers[0]
