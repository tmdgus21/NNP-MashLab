# Schema v2.1 (`db_v21`)

Application ORM. `server-api/models.py` re-exports these models with legacy field
aliases for `workflow.py` / `admin/*`. Target database name: `mashlab_v21`.

## Table count

22 tables. Alembic head: **`20261101_0004`** (`alembic.v21.ini`).

- Rooms carry API compat columns: `progress_status`, `meeting_settings`, `dirty`,
  `current_round`, `host_member_id`
- `idempotency_records.payload` stores extension replay snapshots
- **No** `room_cycles` / cycle archives

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
# alembic -c alembic.v21.ini current   # → 20261101_0004
```

Do not change live `.env` `DB_NAME` or `deploy.sh` until cutover is approved.
