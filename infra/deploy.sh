#!/usr/bin/env bash
# v2.1 FastAPI deploy: migrate potato_server_v2 only, then roll the API container.
# Never drop databases. Never point Alembic v21 at the legacy ok_* DB.
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/conditional-ok-deploy.lock
flock -n 9 || { echo 'Another deployment is running'; exit 1; }

compose=(docker compose -f docker-compose.yml -f docker-compose.ai.yml)
readonly V21_DB_NAME="${V21_DB_NAME:-potato_server_v2}"
readonly LEGACY_DB_NAMES=("mashpotato-server-db")

load_db_name() {
  local name="" file raw
  for file in .env.database .env; do
    if [[ -f "$file" ]]; then
      raw=$(grep -E '^[[:space:]]*DB_NAME=' "$file" | tail -n1 || true)
      [[ -z "$raw" ]] && continue
      name=${raw#*=}
      name=${name%%#*}
      name=${name//[$'\t\r\n \"']/}
      [[ -n "$name" ]] && break
    fi
  done
  printf '%s' "${name}"
}

assert_v21_database_target() {
  local db_name url
  db_name="$(load_db_name)"
  url="${DATABASE_URL:-}"
  if [[ -z "$db_name" ]]; then
    echo "DB_NAME is missing in .env.database / .env. Refusing v2.1 deploy." >&2
    exit 1
  fi
  if [[ "$db_name" != "$V21_DB_NAME" ]]; then
    echo "v2.1 deploy expects DB_NAME=${V21_DB_NAME} (got '${db_name}')." >&2
    echo "Update host env files before deploying; do not migrate the legacy ok_* database." >&2
    exit 1
  fi
  for legacy in "${LEGACY_DB_NAMES[@]}"; do
    if [[ "$db_name" == "$legacy" ]]; then
      echo "Refusing to run Alembic v21 against legacy database '${legacy}'." >&2
      exit 1
    fi
    if [[ "$url" == *"/${legacy}"* || "$url" == *"/${legacy}?"* ]]; then
      echo "DATABASE_URL points at legacy database '${legacy}'. Refusing deploy." >&2
      exit 1
    fi
  done
  if [[ -n "$url" && "$url" != *"/${V21_DB_NAME}"* ]]; then
    echo "DATABASE_URL is set but does not reference ${V21_DB_NAME}. Refusing deploy." >&2
    exit 1
  fi
  echo "Preflight OK: Alembic v21 target DB_NAME=${db_name}"
}

assert_v21_database_target
python3 infra/backup_database.py
previous=$(docker inspect backend-api --format '{{.Image}}')
"${compose[@]}" build server-api
"${compose[@]}" run --rm --no-deps -e DATABASE_URL=sqlite:// -e ADMIN_ENABLED=0 \
  server-api python -m unittest discover -s tests -v
# Schema ownership for v2.1: alembic.v21.ini + migrations_v21 (not legacy alembic.ini / ok_*)
"${compose[@]}" run --rm --no-deps server-api alembic -c alembic.v21.ini upgrade head
"${compose[@]}" run --rm --no-deps server-api alembic -c alembic.v21.ini current
"${compose[@]}" up -d --no-deps server-api
for attempt in {1..30}; do
  if docker exec backend-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)"; then
    echo "FastAPI deployment healthy; DB=${V21_DB_NAME}; Caddy and Qwen preserved"
    exit 0
  fi
  sleep 2
done
image=$(docker inspect backend-api --format '{{.Config.Image}}')
docker tag "$previous" "$image"
"${compose[@]}" up -d --no-deps server-api
echo 'Health check failed; prior image restored. Additive schema retained (no DB drop).' >&2
exit 1
