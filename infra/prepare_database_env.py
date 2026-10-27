"""Build .env.database from root .env for external PostgreSQL (no docker postgres)."""
import os
import pathlib
import secrets
import subprocess

root = pathlib.Path(__file__).resolve().parent.parent
dotenv = {}
env_path = root / ".env"
if env_path.is_file():
    for line in env_path.read_text().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator:
            dotenv[key] = value.strip().strip('"').strip("'")

required = ("DB_USER", "DB_PASSWORD", "DB_NAME")
missing = [key for key in required if not dotenv.get(key)]
if missing:
    raise SystemExit(f".env missing required keys: {', '.join(missing)}")

settings = {
    "DB_HOST": dotenv.get("DB_HOST", "172.19.0.1"),
    "DB_PORT": dotenv.get("DB_PORT", "5432"),
    "DB_USER": dotenv["DB_USER"],
    "DB_PASSWORD": dotenv["DB_PASSWORD"],
    "DB_NAME": dotenv["DB_NAME"],
}
target = root / ".env.database"
prior = dict(line.split("=", 1) for line in target.read_text().splitlines() if "=" in line) if target.is_file() else {}
settings["APP_SESSION_SECRET"] = prior.get("APP_SESSION_SECRET") or secrets.token_hex(32)
if any("\n" in value or "\r" in value for value in settings.values()):
    raise ValueError("Unsupported multiline database environment value")
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as stream:
    stream.write("\n".join(f"{key}={value}" for key, value in settings.items()) + "\n")
os.chmod(target, 0o600)

client_env = {**os.environ, "PGPASSWORD": settings["DB_PASSWORD"]}
subprocess.run(
    [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-e",
        "PGPASSWORD",
        "postgres:18-alpine",
        "psql",
        "-h",
        settings["DB_HOST"],
        "-p",
        settings["DB_PORT"],
        "-U",
        settings["DB_USER"],
        "-d",
        settings["DB_NAME"],
        "-c",
        "SELECT tablename FROM pg_tables WHERE schemaname='public';",
    ],
    env=client_env,
    check=True,
)
print("External Postgres environment prepared; credentials not displayed.")
