from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from potato_agent.graph import open_local_graph
from potato_agent.llama_cpp import (
    LlamaCppClient,
    LlamaCppConfig,
    LocalSnapshotReadTools,
    QwenProposalAgent,
)
from potato_agent.models import MeetingSnapshot
from potato_agent.ortools_adapter import CpSatSolverAdapter
from potato_agent.qwen_proposals import (
    LocalProposalApprovalAdapter,
    ProposalActor,
    RescheduleProposal,
)


def propose_reschedule(
    request_text: str,
    snapshot: MeetingSnapshot,
    actor: ProposalActor,
    *,
    config: LlamaCppConfig | None = None,
    today: date | None = None,
) -> RescheduleProposal:
    agent = QwenProposalAgent(
        client=LlamaCppClient(config),
        tools=LocalSnapshotReadTools(snapshot),
    )
    return agent.propose(request_text, snapshot, actor, today=today)


def confirm_and_recompute(
    snapshot: MeetingSnapshot,
    actor: ProposalActor,
    proposal: RescheduleProposal,
    *,
    checkpoint_path: str | Path,
    thread_id: str,
    today: date | None = None,
    solver_time_limit_seconds: float = 5.0,
) -> tuple[MeetingSnapshot, dict[str, Any]]:
    if not thread_id.strip():
        raise ValueError("A local LangGraph thread ID is required.")

    updated_snapshot = LocalProposalApprovalAdapter().approve(
        snapshot, actor, proposal, today=today
    )
    solver = CpSatSolverAdapter(
        updated_snapshot,
        time_limit_seconds=solver_time_limit_seconds,
    )
    with open_local_graph(solver, checkpoint_path) as graph:
        state = graph.invoke(
            {"meeting_id": updated_snapshot.meeting_id},
            config={"configurable": {"thread_id": thread_id}},
        )
    return updated_snapshot, state
