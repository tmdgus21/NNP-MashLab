from __future__ import annotations

from potato_agent.fixtures import sample_snapshot
from potato_agent.models import AgentStatus
from potato_agent.qwen_proposals import (
    ProposalActor,
    ProposalStatus,
    RescheduleProposalDraft,
    validate_proposal,
)
from potato_agent.qwen_workflow import confirm_and_recompute


def test_confirmed_proposal_runs_langgraph_and_validates_cpsat_candidates(tmp_path):
    snapshot = sample_snapshot()
    actor = ProposalActor(participant_id="organizer-1")
    draft = RescheduleProposalDraft.model_validate(
        {
            "base_input_revision": snapshot.input_revision,
            "changes": [{"kind": "SET_DURATION", "duration_minutes": 45}],
            "summary": "45분으로 변경합니다.",
        }
    )
    proposal = validate_proposal(
        snapshot,
        actor,
        draft,
        today=snapshot.dates[0],
    )

    assert proposal.status == ProposalStatus.PROPOSED
    assert snapshot.input_revision == 7
    assert snapshot.duration_minutes == 60

    updated, state = confirm_and_recompute(
        snapshot,
        actor,
        proposal,
        checkpoint_path=tmp_path / "qwen-agent.sqlite",
        thread_id="confirmed-qwen-proposal",
        today=snapshot.dates[0],
    )

    assert updated.input_revision == 8
    assert updated.consent_round == snapshot.consent_round + 1
    assert updated.duration_minutes == 45
    assert updated.run_id != snapshot.run_id
    assert updated.input_snapshot_hash != snapshot.input_snapshot_hash
    assert state["status"] == AgentStatus.ALL_AVAILABLE
    assert state["candidates"]
    assert all(candidate.verified for candidate in state["candidates"])
    assert all(
        candidate.source_revision == updated.input_revision
        for candidate in state["candidates"]
    )
    assert all(
        candidate.end_minute - candidate.start_minute == 45
        for candidate in state["candidates"]
    )
