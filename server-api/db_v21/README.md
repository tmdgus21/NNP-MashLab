# Schema v2.1 (`db_v21`)

Parallel ORM for the new database (`mashlab_v21`). Legacy `ok_*` models remain in
`models.py` / `admin/models.py` until cutover.

## Table count

- Core v2.1 design: 19 tables  
- Admin security extras: `admin_otps`, `admin_rate_limits`  
- Idempotency ledger: `idempotency_records` (replaces `ok_room_cycles` request pairing)  
- **Removed:** `room_cycle_archives` / multi-event cycles — one event per room; re-runs use `proposals.round`

Total after head `20261101_0002`: **22 tables**.

## Write rules (JSON vs normalized)

| Area | Source of truth for queries | Snapshot / extras |
|------|-----------------------------|-------------------|
| Conditions | `condition_available_slots`, `condition_role_preferences` | `condition_submissions.confirmed` |
| Proposals | `proposal_condition_inputs`, `proposal_assignments`, `proposal_consents` | `proposals.input_snapshot`, `proposals.plan` |
| AI | — | `ai_drafts.model_output`, `app_draft`, `questions` |

On write, derive normalized rows from the same payload stored in JSON so they never diverge.

## Idempotency

- **Create / join:** `room_members.request_key_hash` + `request_hash` (same as `ok_members`)  
- **Other mutations (admin extend, etc.):** `idempotency_records` (`scope`,`key_hash`) UNIQUE  

Same key + different hash → reject (409). Same key + same hash → replay.

## Verification (non-production)

```sh
cd server-api
# disposable sqlite
set DATABASE_URL=sqlite:///./_v21_check.db
alembic -c alembic.v21.ini upgrade head
alembic -c alembic.v21.ini current
python -m unittest tests.test_v21_schema -v
```

Against empty `mashlab_v21` (only after confirming DB is empty; never against `mashpotato-server-db`):

```sh
set DATABASE_URL=postgresql+psycopg://USER:PASS@127.0.0.1:5432/mashlab_v21
alembic -c alembic.v21.ini upgrade head
```

Do not change live `.env` `DB_NAME` or `deploy.sh` until cutover is approved.
