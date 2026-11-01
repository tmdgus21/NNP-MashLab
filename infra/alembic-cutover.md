# Alembic cutover (historical ok_* path)

> **Superseded for production.** Deploy and v2.1 schema use  
> [`infra/alembic-v21-cutover.md`](alembic-v21-cutover.md) with  
> `alembic -c alembic.v21.ini` and `migrations_v21/`.  
> Do **not** follow the commands below against `potato_server_v2` or live traffic.

`database.initialize()` only checks connectivity (and `create_all` for `sqlite://` unit tests). Schema DDL for the running app is owned by Alembic **v2.1**.

## Current (v2.1) commands

```sh
cd server-api
alembic -c alembic.v21.ini upgrade head
alembic -c alembic.v21.ini current
# expect 20261101_0004 (or newer head)
```

Compose (DB_* from env_file / compose; target must be `potato_server_v2`):

```sh
docker compose -f docker-compose.yml -f docker-compose.ai.yml run --rm --no-deps server-api \
  alembic -c alembic.v21.ini upgrade head
```

`infra/deploy.sh` already runs `alembic.v21.ini` after backup and unit tests. It refuses `DB_NAME=mashpotato-server-db`.

Admin tables are part of the v2.1 chain — **do not** run `migrations/legacy/003_admin.py`.

## Legacy ok_* tree (history only)

| Path | Role |
|------|------|
| `server-api/alembic.ini` / `alembic.local.ini` | Points at `migrations/` (ok_*). **Not** used by deploy. |
| `server-api/migrations/` | ok_* baseline revisions |
| `server-api/migrations/legacy/003_admin.py` | Broken pre-v2.1 admin script; quarantined |

Never mix:

- `alembic -c alembic.ini` → only historical `mashpotato-server-db` / ok_* (if ever needed; requires separate approval)
- `alembic -c alembic.v21.ini` → only `potato_server_v2`

## Backup restore drill

```sh
python3 infra/backup_database.py --verify-restore
```

Restores into an isolated `v21_restore_check_*` database, checks `rooms` and `alembic_version`, then drops that DB. It does **not** restore into the configured production `DB_NAME`.
