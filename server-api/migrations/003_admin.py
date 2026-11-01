"""Explicit additive migration. Never called automatically by FastAPI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from database import engine, Room
from sqlalchemy.orm import Session
from admin.models import AdminBase
from admin.lifecycle import ensure
from sqlalchemy import select

def upgrade():
    with engine().begin() as connection:
        if connection.dialect.name == 'postgresql': connection.execute(text('SELECT pg_advisory_xact_lock(781926441)'))
        AdminBase.metadata.create_all(connection)
        with Session(bind=connection) as db:
            for room in db.scalars(select(Room)).yield_per(200): ensure(db, room)
            db.flush()
        connection.execute(text('INSERT INTO ok_schema_versions(version, applied_at) VALUES (3, CURRENT_TIMESTAMP) ON CONFLICT (version) DO NOTHING'))
if __name__ == '__main__':
    if '--apply' not in sys.argv: raise SystemExit('No changes made. Explicit --apply required; never run against production without approval.')
    upgrade()
