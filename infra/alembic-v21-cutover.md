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
| `server-api/db_v21/` | SQLAlchemy models (22 tables) |
| `server-api/models.py` | App entry — re-exports `db_v21` with legacy aliases |
| `server-api/workflow.py` / `admin/*` | **Ported** to v2.1 |
| `server-api/alembic.v21.ini` | Alembic config |
| `server-api/migrations_v21/` | `0001` → `0002` → `0003` → **`0004` (head)** |
| `server-api/tests/test_v21_schema.py` | Disposable sqlite upgrade + inspector |

Legacy `deploy.sh` `alembic -c alembic.ini` remains on **ok_*** until cutover.

## Schema decisions (final)

1. **Auth:** `accounts` + `account_sessions` + `password_reset_tokens`; nicknames on `room_members`.
2. **Idempotency:** create/join on `room_members`; other scopes on `idempotency_records` (+ `payload`).
3. **AI / condition / proposal JSON** restored with normalized companion tables.
4. **No `room_cycles`:** extend uses idempotency ledger; cycle meta in `meeting_settings._lifecycle`.
5. **API compat on rooms:** `progress_status`, `meeting_settings`, `dirty`, `current_round`, `host_member_id`.

## Apply to empty `mashlab_v21` only

1. Backup production: `python3 infra/backup_database.py`
2. Confirm `mashlab_v21` has **no application tables**.
3. Run (session env — do not overwrite production `.env` yet):

```sh
cd server-api
export DATABASE_URL='postgresql+psycopg://USER:PASS@127.0.0.1:5432/mashlab_v21'
alembic -c alembic.v21.ini upgrade head
alembic -c alembic.v21.ini current   # expect 20261101_0004
python -m unittest tests.test_v21_schema tests.test_workflow tests.test_admin tests.test_user_auth -v
```

## Production cutover (requires separate approval)

1. Backup `mashpotato-server-db`.
2. Ensure `mashlab_v21` is at head **`20261101_0004`**.
3. Stop writes / drain traffic.
4. Point root `.env` `DB_NAME` / `DATABASE_URL` to `mashlab_v21`.
5. Switch deploy Alembic to v21:

```sh
# infra/deploy.sh (after approval)
alembic -c alembic.v21.ini upgrade head
```

6. Redeploy FastAPI; verify meetings + admin OTP/session.
7. Keep old DB for a retention window; **delete only after explicit approval**.

## Done in code / still blocked on approval

| Done | Needs approval |
|------|----------------|
| ORM + workflow/admin port | `alembic.v21.ini upgrade` on `mashlab_v21` |
| Unit tests (sqlite) | Live `.env` `DB_NAME` switch |
| Migration `0003` | `deploy.sh` → v21 Alembic |
| | Data migration (none planned) / drop old DB |
