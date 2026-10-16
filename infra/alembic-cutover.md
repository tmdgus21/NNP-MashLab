# Alembic cutover (ok_* schema)

Schema DDL is managed by Alembic. `database.initialize()` only checks connectivity (and creates tables for `sqlite://` unit tests).

## Empty / new database

```sh
cd server-api
# local
alembic -c alembic.local.ini upgrade head
# or in compose (DB_* from env_file / compose)
docker compose run --rm --no-deps server-api alembic -c alembic.ini upgrade head
```

## Existing production database (tables already present)

Do **not** run `upgrade` first if tables already exist; that would try to recreate them.

1. Backup: `python3 infra/backup_database.py`
2. Confirm schema matches baseline (`ok_*` tables from former `database.initialize()` v1..2)
3. Register baseline only:

```sh
docker compose -f docker-compose.yml -f docker-compose.ai.yml run --rm --no-deps server-api alembic -c alembic.ini stamp head
```

4. Later schema changes: add a new revision, then `alembic upgrade head` on deploy (`infra/deploy.sh` already runs upgrade).

## Verify (non-production)

```sh
alembic -c alembic.local.ini check
alembic -c alembic.local.ini current
```
