"""Database engine, sessions, and process init. Schema DDL is owned by Alembic."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import (
    AIDraft,
    Base,
    ConsentRow,
    Member,
    Proposal,
    Room,
    RoomEvent,
    SchemaVersion,
    Submission,
    now,
    uid,
)

__all__ = [
    "AIDraft",
    "Base",
    "ConsentRow",
    "Member",
    "Proposal",
    "Room",
    "RoomEvent",
    "SchemaVersion",
    "Submission",
    "engine",
    "initialize",
    "make_engine",
    "now",
    "session",
    "uid",
]


def make_engine():
    url = os.getenv("DATABASE_URL")
    if url:
        return create_engine(url, **({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} if url == "sqlite://" else {}))
    return create_engine(URL.create("postgresql+psycopg", username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], host=os.getenv("DB_HOST", "172.19.0.1"), port=int(os.getenv("DB_PORT", "5432")), database=os.environ["DB_NAME"]), pool_pre_ping=True)


_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def session():
    return sessionmaker(engine(), expire_on_commit=False)()


def initialize():
    """Verify connectivity. PostgreSQL schema is managed by Alembic.
    sqlite:// unit tests create tables from metadata for isolation."""
    with engine().begin() as connection:
        if connection.dialect.name == "sqlite":
            Base.metadata.create_all(connection)
            return
        connection.execute(text("SELECT 1"))


if __name__ == "__main__":
    initialize()
    print("Database connection OK; apply schema with: alembic upgrade head")
