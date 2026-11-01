"""LEGACY — broken after v2.1. Do not run.

Historical ok_* admin additive script. It depended on AdminBase, which was removed
when admin tables moved into db_v21 / alembic.v21. Kept under migrations/legacy/
for reference only. Use: alembic -c alembic.v21.ini upgrade head
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def upgrade():
    raise SystemExit(
        "Refusing to run legacy 003_admin. Admin schema is owned by "
        "alembic.v21.ini / migrations_v21 (db_v21). See migrations/legacy/README.md."
    )
    # Historical body (unreachable). Left for archaeology; AdminBase no longer exists.
    from sqlalchemy import select, text  # pragma: no cover
    from sqlalchemy.orm import Session  # pragma: no cover

    from admin.lifecycle import ensure  # pragma: no cover
    from admin.models import AdminBase  # pragma: no cover
    from database import Room, engine  # pragma: no cover

    with engine().begin() as connection:  # pragma: no cover
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(781926441)"))
        AdminBase.metadata.create_all(connection)
        with Session(bind=connection) as db:
            for room in db.scalars(select(Room)).yield_per(200):
                ensure(db, room)
            db.flush()
        connection.execute(
            text(
                "INSERT INTO ok_schema_versions(version, applied_at) "
                "VALUES (3, CURRENT_TIMESTAMP) ON CONFLICT (version) DO NOTHING"
            )
        )


if __name__ == "__main__":
    raise SystemExit(
        "No changes made. This script is legacy-quarantined; never run against "
        "potato_server_v2 or mashpotato-server-db. Use alembic.v21.ini instead."
    )
