"""Local-only Potato Meet Agent Core experiment."""

from importlib import import_module
from typing import Any

from potato_agent.models import AgentStatus, MeetingSnapshot

__all__ = [
    "AgentStatus",
    "CpSatSolverAdapter",
    "FixtureToolAdapter",
    "MeetingSnapshot",
    "build_agent_graph",
    "open_local_graph",
]


def __getattr__(name: str) -> Any:
    module_names = {
        "build_agent_graph": "potato_agent.graph",
        "open_local_graph": "potato_agent.graph",
        "CpSatSolverAdapter": "potato_agent.ortools_adapter",
        "FixtureToolAdapter": "potato_agent.tools",
    }
    module_name = module_names.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)
