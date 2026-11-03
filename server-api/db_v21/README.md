# Schema v2.1 (`db_v21`)

Application ORM. `server-api/models.py` re-exports these models with legacy field
aliases for `workflow.py` / `admin/*`. Production target database name: `potato_server_v2`.

## Table count

26 tables. Alembic head: **`20261102_0007`** (`alembic.v21.ini`).

- Rooms carry API compat columns: `progress_status`, `meeting_settings`, `dirty`,
  `current_round`, `host_member_id`
- `idempotency_records.payload` stores extension replay snapshots
- **No** `room_cycles` / cycle archives
- Agent Core adds `rooms.agent_input_revision` and the `room_invitations`,
  `agent_runs`, `agent_candidates`, and `agent_candidate_members` tables.
- Agent-run start idempotency uses `idempotency_records` with a coordination
  scope and request hash; run creation and replay recording must be atomic.
- Agent candidate consent and run snapshots are isolated from v1 proposal and
  consent records; Agent approval does not finalize a room.

`rooms.meeting_settings.coordination` uses `schemaVersion: 1` with required
`activity`, `location`, `durationMinutes`, `dates`, `timeZone` (`Asia/Seoul`),
and host-set `minimumAttendeeCount`. Optional `excludedDates`,
`requiredStartMinutesByDate`, and `absoluteTimeWindows` map directly to
`MeetingSnapshot`; unknown fields and unsupported versions are rejected.
The Snapshot Builder selects the highest `condition_submissions.version` per
active member, normalizes/merges one-minute Seoul slots, and reads only
`rooms.agent_input_revision` (not the broader v1 `rooms.revision`). Its
SHA-256 input hash excludes run/session IDs and consent round. Callers must
close the read session before handing the detached Snapshot to Agent execution.

`services.agent_run.start_agent_run` verifies an active USER account and active
room membership, compares `expectedInputRevision`, and persists a `QUEUED`
`agent_runs` row with the immutable snapshot and a hashed idempotency record in
one transaction. Run creation is member-authorized, not host-only; host actions
must separately call `authorize_room_host`. Non-null `userRequest` is rejected
until the Run schema can persist it. Revision `20261102_0006` adds `QUEUED`
without editing earlier revisions; downgrade is blocked while queued runs
remain. SQLite tests verify atomic behavior but do not establish PostgreSQL
concurrency guarantees.

`services.agent_solver.run_agent_solver` consumes that detached queued Run and
reuses the Agent Core LangGraph, CP-SAT adapter, and candidate validator. It
checks the current `agent_input_revision` and rebuilt snapshot hash using
short-lived read sessions before/during/after solving; no DB session spans
CP-SAT. Only a proven all-attendee `INFEASIBLE` result reaches partial search.
The function returns validated candidates at the graph's candidate-selection
pause; it does not persist solver state or candidates. The current in-memory
checkpointer is the default (process-local); a durable checkpointer
(PostgreSQL, see DEPLOY-AGENT-WORKER.md) can be passed per worker, and
`services.agent_resume` resumes paused Runs from it after revalidating the DB. LangGraph is pinned in the server
requirements for this service.

`services.agent_worker` claims queued Runs using `FOR UPDATE SKIP LOCKED`,
records a hashed lease token, and renews the lease with short independent
transactions while solver execution has no open DB session. Expired leases may
be reclaimed up to three attempts; retryable solver failures may be requeued
without changing the immutable snapshot. The additive `20261102_0007`
revision adds explicit `RUNNING` and `FAILED` states and blocks downgrade while
either state is stored. Cancellation immediately terminates queued Runs and is
cooperative for active workers. Completion locks the room and Run, checks the
lease/cancellation/rebuilt snapshot revision and hash, then stores ranked
candidate rows and attending/unavailable room-member rows in the same
transaction as the terminal Run state. Candidate ranks are limited to 1..3;
existing candidate and consent history is never replaced. PostgreSQL row-lock
and lease race behavior still requires isolated PostgreSQL concurrency tests.

## Write rules (JSON vs normalized)

| Area | Source of truth for queries | Snapshot / extras |
|------|-----------------------------|-------------------|
| Conditions | `condition_available_slots`, `condition_role_preferences` | `condition_submissions.confirmed` |
| Proposals | `proposal_condition_inputs`, `proposal_assignments`, `proposal_consents` | `proposals.input_snapshot`, `proposals.plan` |
| AI | — | `ai_drafts.model_output`, `app_draft`, `questions` |

## Idempotency

- **Create / join:** `room_members.request_key_hash` + `request_hash`
- **Extend / other:** `idempotency_records` (`scope`, `key_hash`) UNIQUE

## Verification (non-production)

```sh
cd server-api
python -m unittest tests.test_v21_schema tests.test_workflow tests.test_admin -v

# empty mashlab_v21 only (after approval)
# set DATABASE_URL=postgresql+psycopg://USER:PASS@127.0.0.1:5432/mashlab_v21
# alembic -c alembic.v21.ini upgrade head
# alembic -c alembic.v21.ini current   # → 20261102_0007
```

Do not change live `.env` `DB_NAME` or `deploy.sh` until cutover is approved.
