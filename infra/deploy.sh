#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/conditional-ok-deploy.lock
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
compose=(docker compose -f docker-compose.yml -f docker-compose.ai.yml)
python3 infra/backup_database.py
previous=$(docker inspect backend-api --format '{{.Image}}')
"${compose[@]}" build server-api
"${compose[@]}" run --rm --no-deps -e DATABASE_URL=sqlite:// server-api python -m unittest discover -s tests -v
"${compose[@]}" run --rm --no-deps server-api alembic -c alembic.ini upgrade head
"${compose[@]}" up -d --no-deps server-api
for attempt in {1..30}; do
  if docker exec backend-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)"; then
    echo 'FastAPI deployment healthy; database, Caddy and Qwen preserved'
    exit 0
  fi
  sleep 2
done
image=$(docker inspect backend-api --format '{{.Config.Image}}')
docker tag "$previous" "$image"
"${compose[@]}" up -d --no-deps server-api
echo 'Health check failed; prior image restored. Additive schema retained.' >&2
exit 1
