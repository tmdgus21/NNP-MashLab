# Alembic v2.1 cutover (empty DB replace — no data migration)

Parallel to legacy `ok_*` ([alembic-cutover.md](alembic-cutover.md)).  
**Do not drop or reset the production database without explicit operator approval.**

## What was added

| Path | Role |
|------|------|
| `server-api/db_v21/` | SQLAlchemy models: 19 v2.1 tables + 3 admin security extras |
| `server-api/alembic.v21.ini` | Alembic config for the v2.1 chain |
| `server-api/migrations_v21/` | Versions (head: `20261101_0001`) |
| `server-api/tests/test_v21_schema.py` | Disposable sqlite upgrade + inspector checks |

Legacy `server-api/migrations/` + `deploy.sh` `alembic -c alembic.ini upgrade head` remain on **ok_*** until cutover.

## Admin extras (beyond core 19)

- `admin_otps` — OTP challenges  
- `admin_rate_limits` — rate buckets  
- `room_cycle_archives` — cycle snapshots  

Accounts with `account_type=ADMIN` carry `admin_role`, `approved`, `failures`, `revision`.

## Dev / empty database (safe)

1. Create a **new** database on the same PostgreSQL server (example name only): `mashlab_v21_dev`.
2. Point a **non-production** URL at it, e.g. set `DATABASE_URL` for the session (do not overwrite production `.env` until approved).
3. From `server-api`:

```sh
alembic -c alembic.v21.ini upgrade head
alembic -c alembic.v21.ini current
```

4. Run schema test:

```sh
python -m unittest tests.test_v21_schema -v
```

5. Inspect tables/FKs/UNIQUEs; fix only via new revisions (never `create_all` in production).

## Production cutover (requires separate approval)

1. Backup: `python3 infra/backup_database.py`
2. Create empty production-candidate DB (new name).
3. `alembic -c alembic.v21.ini upgrade head` against that DB only.
4. Stop writes / drain traffic.
5. Point root `.env` `DB_NAME` / `DATABASE_URL` to the new DB.
6. Switch deploy to v21 Alembic, e.g. change [`infra/deploy.sh`](deploy.sh) to:

```sh
alembic -c alembic.v21.ini upgrade head
```

7. Redeploy FastAPI; verify API + admin.
8. Keep the old DB for a retention window; **delete only after explicit approval**.

## Not done in this phase

- Rewriting `workflow.py` / `admin/*.py` onto v2.1 models  
- Changing GitHub Actions or live `DB_NAME`  
- Data migration from `ok_*`  

## Open design notes

- Audit targets: polymorphic `target_type` / `target_id` (no hard FK).  
- Assignment time overlap: app-level first; PG exclusion constraints later.  
- Single OWNER per room: service transaction first; partial unique later.  
- Soft-delete rooms via `rooms.deleted_at`; 30-day physical purge is a future batch job.
