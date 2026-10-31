"""Private PostgreSQL backups against external DB; optional isolated restore drill."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--verify-restore", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


env = load_env(root / ".env.database")
if not env.get("DB_USER") or not env.get("DB_PASSWORD") or not env.get("DB_NAME"):
    fallback = load_env(root / ".env")
    for key in ("DB_USER", "DB_PASSWORD", "DB_NAME", "DB_HOST", "DB_PORT"):
        env.setdefault(key, fallback.get(key, ""))

missing = [key for key in ("DB_USER", "DB_PASSWORD", "DB_NAME") if not env.get(key)]
if missing:
    sys.exit(
        ".env.database(또는 .env)에 "
        + ", ".join(missing)
        + " 가 없습니다. 먼저 python3 infra/prepare_database_env.py 를 실행하세요."
    )

# Containers on mash-net use the docker bridge gateway (e.g. 172.19.0.1).
# This script runs on the host with --network host, so use loopback unless overridden.
configured_host = env.get("DB_HOST", "172.19.0.1")
host = os.getenv("DB_BACKUP_HOST") or (
    "127.0.0.1" if configured_host.startswith("172.") or configured_host in {"host.docker.internal", "postgres"} else configured_host
)
port = env.get("DB_PORT", "5432")
backup_root = Path("/home/linuxuser/conditional-ok-backups/postgres")
backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(backup_root, 0o700)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
target = backup_root / f"conditional-ok-{stamp}.dump"
client_env = {**os.environ, "PGPASSWORD": env["DB_PASSWORD"]}


def pg_client(args_list, **kwargs):
    try:
        return subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--network",
                "host",
                "-e",
                "PGPASSWORD",
                "postgres:18-alpine",
                *args_list,
            ],
            env=client_env,
            check=True,
            **kwargs,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"PostgreSQL client failed (host={host} port={port} db={env['DB_NAME']} user={env['DB_USER']}): "
            f"exit {exc.returncode}. Check DB listen address, credentials, and docker permissions."
        ) from exc


print(f"Backing up {env['DB_NAME']} via {host}:{port} ...")
with target.open("xb") as output:
    os.chmod(target, 0o600)
    pg_client(
        ["pg_dump", "-h", host, "-p", port, "-U", env["DB_USER"], "-d", env["DB_NAME"], "-Fc", "--no-owner", "--no-acl"],
        stdout=output,
    )
with target.open("rb") as source:
    pg_client(["pg_restore", "--list"], stdin=source, stdout=subprocess.DEVNULL)
secret_source = root / ".env.database"
if not secret_source.is_file():
    secret_source = root / ".env"
secret_copy = backup_root / f"conditional-ok-{stamp}.env"
shutil.copyfile(secret_source, secret_copy)
os.chmod(secret_copy, 0o600)
if args.verify_restore:
    database = "ok_restore_check_" + stamp.lower()
    assert re.fullmatch(r"ok_restore_check_\d{8}t\d{6}z", database)
    pg_client(["createdb", "-h", host, "-p", port, "-U", env["DB_USER"], database])
    try:
        with target.open("rb") as source:
            pg_client(
                [
                    "pg_restore",
                    "-h",
                    host,
                    "-p",
                    port,
                    "-U",
                    env["DB_USER"],
                    "-d",
                    database,
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                ],
                stdin=source,
            )
        pg_client(
            [
                "psql",
                "-h",
                host,
                "-p",
                port,
                "-U",
                env["DB_USER"],
                "-d",
                database,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT count(*) AS restored_rooms FROM ok_rooms;",
            ]
        )
        print("Isolated database restore drill PASS")
    finally:
        pg_client(["dropdb", "-h", host, "-p", port, "-U", env["DB_USER"], database])
cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - 14 * 86400
for old in backup_root.iterdir():
    if old.is_file() and re.fullmatch(r"conditional-ok-\d{8}T\d{6}Z\.(dump|env)", old.name) and old.stat().st_mtime < cutoff:
        old.unlink()
print(f"Backup validated: {target} ({target.stat().st_size} bytes); permissions 0600")
