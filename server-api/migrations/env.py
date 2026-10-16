from logging.config import fileConfig
import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL

from models import Base

config = context.config

# Local overrides first; process env (Docker/CI) wins when already set.
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)


def resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    name = os.environ.get("DB_NAME")
    if not (user and password and name):
        raise RuntimeError(
            "DATABASE_URL 또는 DB_USER/DB_PASSWORD/DB_NAME이 필요합니다. "
            "로컬은 server-api/.env.local을 사용하세요."
        )
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=name,
    ).render_as_string(hide_password=False)


config.set_main_option("sqlalchemy.url", resolve_database_url().replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
