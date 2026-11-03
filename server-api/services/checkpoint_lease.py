"""Single DB lease guarding every writer of a Run's graph checkpoint.

Both services.agent_decision (rebuild from the DB) and services.agent_resume
(low-level resume) must hold this lease before touching the checkpoint or
``agent_runs.checkpoint_ref``. It is one conditional UPDATE, so exactly one
process wins; an expired lease (crashed owner) can be taken over.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentRun

SessionFactory = Callable[[], Session]
LEASE_SECONDS = 30


def claim_lease(
    session_factory: SessionFactory,
    run_id: str,
    owner: str,
    *,
    extra_where: tuple = (),
    lease_seconds: int = LEASE_SECONDS,
) -> bool:
    current = now()
    with session_factory() as db:
        with db.begin():
            result = db.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    or_(
                        AgentRun.sync_owner.is_(None),
                        AgentRun.sync_lease_expires_at <= current,
                    ),
                    *extra_where,
                )
                .values(
                    sync_owner=owner,
                    sync_lease_expires_at=current + timedelta(seconds=lease_seconds),
                )
            )
            return result.rowcount == 1


def release_lease(
    session_factory: SessionFactory, run_id: str, owner: str, **values: Any
) -> bool:
    """Release (and optionally write ``values``) only if ``owner`` still holds it."""
    with session_factory() as db:
        with db.begin():
            result = db.execute(
                update(AgentRun)
                .where(AgentRun.id == run_id, AgentRun.sync_owner == owner)
                .values(sync_owner=None, sync_lease_expires_at=None, **values)
            )
            return result.rowcount == 1
