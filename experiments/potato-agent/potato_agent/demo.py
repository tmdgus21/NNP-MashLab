from __future__ import annotations

import argparse
from pathlib import Path

from potato_agent.fixtures import sample_snapshot
from potato_agent.graph import open_local_graph
from potato_agent.ortools_adapter import CpSatSolverAdapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local fixture-only Potato Meet Agent graph."
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("agent-checkpoints.sqlite"),
        help="Local SQLite checkpoint file (default: agent-checkpoints.sqlite).",
    )
    args = parser.parse_args()

    snapshot = sample_snapshot()
    tools = CpSatSolverAdapter(snapshot)
    with open_local_graph(tools, args.checkpoint) as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config={
                "configurable": {
                    "thread_id": f"local:{snapshot.meeting_id}:{snapshot.run_id}"
                }
            },
        )
    print(f"Status: {result['status'].value}")
    print("Paused for candidate selection. No meeting has been finalized.")
    print(f"Checkpoint: {args.checkpoint}")


if __name__ == "__main__":
    main()
