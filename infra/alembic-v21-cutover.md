# Alembic v2.1 cutover (empty DB replace — no data migration)

Parallel to legacy `ok_*` ([alembic-cutover.md](alembic-cutover.md)).  
**Do not drop or reset the production database without explicit operator approval.**

## Databases

| Role | Name |
|------|------|
| Current production | `mashpotato-server-db` |
| New target (empty) | `mashlab_v21` |

## What is in the repo

| Path | Role |
|------|------|
| `server-api/db_v21/` | SQLAlchemy models (22 tables after finalize) |
| `server-api/alembic.v21.ini` | Alembic config for the v2.1 chain |
| `server-api/migrations_v21/` | `20261101_0001` → `20261101_0002` (head) |
| `server-api/tests/test_v21_schema.py` | Disposable sqlite upgrade + inspector |
| `server-api/db_v21/README.md` | Write rules / verification |

Legacy `server-api/migrations/` + `deploy.sh` `alembic -c alembic.ini upgrade head` remain on **ok_*** until cutover.

## Schema decisions (final)

1. **Auth:** `accounts` + `account_sessions` + `password_reset_tokens`; nicknames on `room_members`.
2. **Idempotency:** `room_members.request_key_hash` / `request_hash` for create/join; `idempotency_records` for other scopes.
3. **AI JSON restored** on `ai_drafts` (`model_output`, `app_draft`, `questions`).
4. **`confirmed` JSON** on `condition_submissions` + normalized slots/preferences.
5. **`input_snapshot` / `plan` JSON** on `proposals` + normalized assignment tables.
6. **No `room_cycles`:** re-assignment increments `proposals.round`; keep prior rounds as INVALIDATED.
7. **Admin security kept:** OTP, sessions (via `account_sessions`), rate limits, audit, room/service controls, announcements.

## Apply to empty `mashlab_v21` only

1. Backup production: `python3 infra/backup_database.py`
2. Confirm `mashlab_v21` has **no application tables** (empty or only unused).
3. Run (example — use a **session** env, do not overwrite production `.env` yet):

```sh
cd server-api
export DATABASE_URL='postgresql+psycopg://USER:PASS@127.0.0.1:5432/mashlab_v21'
alembic -c alembic.v21.ini upgrade head
alembic -c alembic.v21.ini current   # expect 20261101_0002
python -m unittest tests.test_v21_schema -v
```

4. Inspect tables / FKs / UNIQUEs.

## Production cutover (requires separate approval)

1. Backup `mashpotato-server-db`.
2. Ensure `mashlab_v21` is at head and API ported to `db_v21`.
3. Stop writes / drain traffic.
4. Point root `.env` `DB_NAME` / `DATABASE_URL` to `mashlab_v21`.
5. Switch deploy Alembic to v21:

```sh
# infra/deploy.sh (after approval)
alembic -c alembic.v21.ini upgrade head
```

6. Redeploy FastAPI; verify meetings + admin OTP/session.
7. Keep old DB for a retention window; **delete only after explicit approval**.

## Not done until API port + approval

- Rewriting `workflow.py` / `admin/*.py` onto `db_v21` models  
- Changing live `DB_NAME` or GitHub Actions deploy target  
- Data migration from `ok_*`

## Open design notes

- Audit targets: polymorphic `target_type` / `target_id`.  
- Assignment overlap / 30-minute slots: enforce in services; DB CHECK is range-only.  
- Single OWNER per room: service transaction first.  
- Soft-delete via `rooms.deleted_at`.
