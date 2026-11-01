from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace
from typing import Any

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
    RescheduleProposal,
    ProposalStatus,
)
from potato_agent.qwen_workflow import confirm_and_recompute


_AMBIGUITY_CATEGORIES = (
    (
        ("duration", "소요시간", "진행시간"),
        "AMBIGUOUS_DURATION",
        "The model marked the requested duration as unclear; raw text redacted.",
    ),
    (
        ("date", "날짜", "일자"),
        "AMBIGUOUS_DATE",
        "The model marked the requested date as unclear; raw text redacted.",
    ),
    (
        ("time", "시간", "시각", "오전", "오후"),
        "AMBIGUOUS_TIME",
        "The model marked the requested clock time as unclear; raw text redacted.",
    ),
    (
        ("target", "대상"),
        "AMBIGUOUS_TARGET",
        "The model marked the requested change target as unclear; raw text redacted.",
    ),
    (
        ("participant", "참여자", "친구"),
        "AMBIGUOUS_PARTICIPANT",
        "The model marked a participant reference as unclear; raw text redacted.",
    ),
    (
        ("condition", "조건", "시간창"),
        "AMBIGUOUS_CONDITION",
        "The model marked a time-window condition as unclear; raw text redacted.",
    ),
)


def _safe_ambiguity_diagnostics(ambiguities: tuple[str, ...]) -> list[dict[str, str]]:
    diagnostics = []
    for ambiguity in ambiguities:
        normalized = ambiguity.casefold()
        category = next(
            (
                item
                for item in _AMBIGUITY_CATEGORIES
                if any(term in normalized for term in item[0])
            ),
            None,
        )
        if category is None:
            diagnostics.append(
                {
                    "code": "UNCLASSIFIED_AMBIGUITY",
                    "reason": "The model returned clarification text; raw text redacted.",
                }
            )
        else:
            diagnostics.append({"code": category[1], "reason": category[2]})
    return diagnostics


def _proposal_diagnostic(proposal: Any, agent: Any) -> dict[str, Any]:
    changes = [
        {
            "kind": change.kind,
            "duration_minutes": (
                change.duration_minutes
                if change.kind == "SET_DURATION"
                else None
            ),
        }
        for change in proposal.changes
    ]
    runtime = agent.last_diagnostics or {}
    if proposal.status == ProposalStatus.CLARIFICATION_REQUIRED:
        classification_path = (
            "RescheduleIntentExtraction.ambiguities non-empty -> "
            "build_proposal_from_intents -> validate_proposal sets "
            "CLARIFICATION_REQUIRED"
        )
    elif proposal.status == ProposalStatus.PROPOSED:
        classification_path = (
            "build_proposal_from_intents -> validate_proposal accepts proposal"
        )
    else:
        classification_path = "proposal returned with another status"
    regenerations = runtime.get("regenerations", 0)
    return {
        "status": proposal.status.value,
        "changes": changes,
        "ambiguities": _safe_ambiguity_diagnostics(proposal.ambiguities),
        "tool_calls": agent.dispatcher.call_count,
        "verification_retry": bool(regenerations),
        "regenerations": regenerations,
        "model_requests": runtime.get("model_requests", "unavailable"),
        "classification_path": classification_path,
    }


def test_proposal_diagnostic_reports_safe_ambiguity_category_only():
    raw_ambiguity = "target is unclear for private-person@example.com"
    proposal = RescheduleProposal(
        proposal_id="fixture-proposal",
        base_input_revision=7,
        status=ProposalStatus.CLARIFICATION_REQUIRED,
        changes=(),
        ambiguities=(raw_ambiguity,),
        summary="redacted",
    )
    agent = SimpleNamespace(
        last_diagnostics={"regenerations": 1, "model_requests": 2},
        dispatcher=SimpleNamespace(call_count=1),
    )

    diagnostic = _proposal_diagnostic(proposal, agent)
    serialized = json.dumps(diagnostic)

    assert diagnostic["status"] == "CLARIFICATION_REQUIRED"
    assert diagnostic["ambiguities"] == [
        {
            "code": "AMBIGUOUS_TARGET",
            "reason": (
                "The model marked the requested change target as unclear; "
                "raw text redacted."
            ),
        }
    ]
    assert diagnostic["tool_calls"] == 1
    assert diagnostic["verification_retry"] is True
    assert diagnostic["regenerations"] == 1
    assert "validate_proposal sets CLARIFICATION_REQUIRED" in diagnostic[
        "classification_path"
    ]
    assert raw_ambiguity not in serialized
    assert "private-person@example.com" not in serialized


@pytest.mark.skipif(
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
    diagnostic = _proposal_diagnostic(proposal, agent)
    print(
        "LIVE_QWEN_PROPOSAL_DIAGNOSTIC "
        + json.dumps(diagnostic, ensure_ascii=True, sort_keys=True)
    )
    record_property(
        "qwen_proposal_diagnostic",
        json.dumps(diagnostic, ensure_ascii=True, sort_keys=True),
    )

    assert (
        proposal.status == ProposalStatus.PROPOSED
        and proposal.ambiguities == ()
        and len(proposal.changes) == 1
        and proposal.changes[0].kind == "SET_DURATION"
        and proposal.changes[0].duration_minutes == 45
    ), f"Unexpected Qwen proposal: {json.dumps(diagnostic, ensure_ascii=True, sort_keys=True)}"
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
