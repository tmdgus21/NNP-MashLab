"""Reuse existing Postgres credentials without printing or committing them."""
import json
import os
import pathlib
import subprocess
import secrets

container = json.loads(subprocess.check_output(["docker", "inspect", "mashlab-postgres"]))[0]
env = dict(value.split("=", 1) for value in container["Config"]["Env"] if "=" in value)
root = pathlib.Path(__file__).resolve().parent.parent
for candidate in (root / ".env" / ".env", root / ".env" / "a"):
    if candidate.is_file():
        for line in candidate.read_text().splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
                env[key] = value.strip().strip('"').strip("'")
settings = {"DB_HOST": "postgres", "DB_PORT": "5432", "DB_USER": env["POSTGRES_USER"], "DB_PASSWORD": env["POSTGRES_PASSWORD"], "DB_NAME": env.get("POSTGRES_DB", env["POSTGRES_USER"])}
target = pathlib.Path(__file__).resolve().parent.parent / ".env.database"
prior = dict(line.split("=",1) for line in target.read_text().splitlines() if "=" in line) if target.is_file() else {}
settings["APP_SESSION_SECRET"] = prior.get("APP_SESSION_SECRET") or secrets.token_hex(32)
if any("\n" in value or "\r" in value for value in settings.values()):
    raise ValueError("Unsupported multiline database environment value")
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as stream:
    stream.write("\n".join(f"{key}={value}" for key, value in settings.items()) + "\n")
os.chmod(target, 0o600)
subprocess.run(["docker", "exec", "mashlab-postgres", "psql", "-U", settings["DB_USER"], "-d", settings["DB_NAME"], "-c", "SELECT tablename FROM pg_tables WHERE schemaname='public';"], check=True)
print("Existing Postgres environment prepared; credentials not displayed.")
