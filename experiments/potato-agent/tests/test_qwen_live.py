from __future__ import annotations

import os
import time

import pytest

from potato_agent.fixtures import sample_snapshot
from potato_agent.llama_cpp import (
    LlamaCppClient,
    LlamaCppConfig,
    LocalSnapshotReadTools,
    QwenProposalAgent,
)
from potato_agent.models import AgentStatus
from potato_agent.qwen_proposals import (
    ProposalActor,
    ProposalStatus,
)
from potato_agent.qwen_workflow import confirm_and_recompute

pytestmark = pytest.mark.skipif(
    os.environ.get("POTATO_RUN_LIVE_QWEN") != "1",
    reason="Set POTATO_RUN_LIVE_QWEN=1 to run the explicit local Qwen integration.",
)


def test_live_qwen_tool_call_proposal_and_langgraph_recalculation(
    tmp_path, record_property
):
    config = LlamaCppConfig(
        base_url="http://127.0.0.1:18081",
        model="potato-qwen-test",
        request_timeout_seconds=45,
        total_timeout_seconds=120,
    )
    client = LlamaCppClient(config)
    probe = client.probe()
    assert probe["reachable"], f"Local Qwen tunnel unavailable: {probe}"
    assert probe["model_id_verified"], f"Expected model ID not served: {probe}"

    snapshot = sample_snapshot()
    snapshot_before = snapshot.model_dump(mode="json")
    actor = ProposalActor(participant_id="organizer-1")
    agent = QwenProposalAgent(client, LocalSnapshotReadTools(snapshot))
    started_at = time.perf_counter()
    proposal = agent.propose(
        "현재 모임 제약을 확인한 다음, 소요시간을 45분으로 줄여줘.",
        snapshot,
        actor,
        today=snapshot.dates[0],
    )
    inference_seconds = time.perf_counter() - started_at

    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.ambiguities == ()
    assert len(proposal.changes) == 1
    assert proposal.changes[0].kind == "SET_DURATION"
    assert proposal.changes[0].duration_minutes == 45
    assert proposal.base_input_revision == snapshot.input_revision
    assert agent.dispatcher.call_count >= 1
    assert snapshot.model_dump(mode="json") == snapshot_before
    assert snapshot.input_revision == 7
    assert snapshot.consent_round == 1
    assert snapshot.duration_minutes == 60
    record_property("qwen_inference_seconds", inference_seconds)
    print(
        "LIVE_QWEN "
        f"inference_seconds={inference_seconds:.3f} "
        f"tool_calls={agent.dispatcher.call_count} "
        f"model={config.model} endpoint={config.base_url}"
    )

    updated, state = confirm_and_recompute(
        snapshot,
        actor,
        proposal,
        checkpoint_path=tmp_path / "live-qwen-agent.sqlite",
        thread_id="live-qwen-confirmed-replan",
        today=snapshot.dates[0],
    )

    assert updated.input_revision == snapshot.input_revision + 1
    assert updated.duration_minutes == 45
    assert state["status"] == AgentStatus.ALL_AVAILABLE
    assert state["candidates"]
    assert all(candidate.verified for candidate in state["candidates"])
