<<<<<<< HEAD
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
=======
# Alembic v2.1 cutover / production deploy prep

**Do not drop or reset any database without explicit operator approval.**  
**Do not merge to `main` or restart production until cutover is approved.**

## Databases

| Role | Name | Notes |
|------|------|-------|
| Legacy production (keep) | `mashpotato-server-db` | `ok_*` schema — **do not migrate with v21** |
| v2.1 production target | `potato_server_v2` | Empty / new PG 18 DB for FastAPI v2.1 |

`infra/deploy.sh` refuses `DB_NAME=mashpotato-server-db` and requires `DB_NAME=potato_server_v2`.

## Repo wiring (develop)

| Path | Role |
|------|------|
| `server-api/Dockerfile` | `COPY . .` + build-time assert for `alembic.v21.ini` / `migrations_v21` / `db_v21` |
| `docker-compose.yml` | Passes `DB_NAME`, `DB_*`, `DATABASE_URL` into `server-api` |
| `docker-compose.ai.yml` | Loads `.env.database` (host secrets) |
| `infra/deploy.sh` | Backup → unittest → **`alembic -c alembic.v21.ini upgrade head`** → recreate API → healthcheck / image rollback |
| `.github/workflows/gitmain.yml` | **Deploy only on `push` to `main`** |

Legacy `alembic.ini` / `migrations/` remain for history; deploy no longer runs them.

## Pre-cutover checklist (operator)

1. On Ubuntu PG 18 host: create empty DB `potato_server_v2` (no DROP of legacy DB).
2. Backup legacy: `python3 infra/backup_database.py` with env still pointing at legacy **or** set `DB_NAME` temporarily for backup only — prefer backing up legacy explicitly before switching env.
3. Point host `.env` / `.env.database` to:
   - `DB_NAME=potato_server_v2`
   - matching `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT`
   - `DATABASE_URL` empty **or** URL whose path is `/potato_server_v2`
4. Confirm compose injects the name:
   ```sh
   docker compose -f docker-compose.yml -f docker-compose.ai.yml run --rm --no-deps server-api printenv DB_NAME
   # → potato_server_v2
   ```
5. Optional dry-run migration (before main merge):
   ```sh
   docker compose … run --rm --no-deps server-api alembic -c alembic.v21.ini upgrade head
   docker compose … run --rm --no-deps server-api alembic -c alembic.v21.ini current
   # expect 20261101_0004
   ```

## Deploy path (after `main` merge — not done in this prep)

1. Push/merge to `main` → Actions `test` then `deploy` (main push only).
2. `deploy.sh` on host:
   - asserts `DB_NAME=potato_server_v2`
   - backups current configured DB
   - builds image (includes v21 Alembic files)
   - runs unit tests with `DATABASE_URL=sqlite://`
   - `alembic -c alembic.v21.ini upgrade head`
   - `up -d --no-deps server-api`
   - OpenAPI healthcheck; on failure retags previous image and restarts API (**schema changes already applied are kept**; no DROP)

## Rollback

| Layer | Action |
|-------|--------|
| App container | Automatic in `deploy.sh` on failed healthcheck (previous image) |
| Manual app | `docker tag <previous> …` then `compose up -d --no-deps server-api` |
| Database | Restore from `/home/linuxuser/conditional-ok-backups/postgres/*.dump` via `backup_database.py --verify-restore` drill / `pg_restore` into a **new** DB name — never overwrite legacy without approval |
| Traffic | Keep Caddy pointing at API; do not delete `mashpotato-server-db` |

## Anti-mix rules

- v2.1 code + `alembic.v21.ini` → **only** `potato_server_v2`
- Legacy `ok_*` + old app image → **only** `mashpotato-server-db`
- Never run `alembic -c alembic.ini` against `potato_server_v2`
- Never run `alembic -c alembic.v21.ini` against `mashpotato-server-db`

## Local verification (non-prod)

```sh
cd server-api
set DATABASE_URL=sqlite://
set ADMIN_ENABLED=0
python -m unittest discover -s tests -v
python -m unittest tests.test_v21_schema -v
```
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
