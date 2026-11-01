# Legacy admin migration (do not run)

`003_admin.py` targeted the pre–v2.1 `ok_*` / `AdminBase` path. `AdminBase` no longer exists in `admin.models` (admin tables live under `db_v21` and ship via `alembic.v21.ini` / `migrations_v21`).

- **Do not** run `python migrations/legacy/003_admin.py --apply`.
- **Do not** run this against `potato_server_v2` or `mashpotato-server-db`.
- For schema: `alembic -c alembic.v21.ini upgrade head` (see `infra/alembic-v21-cutover.md`).

Kept only as historical reference; the broader `migrations/` + `alembic.ini` tree remains for ok_* history and is not used by deploy.
