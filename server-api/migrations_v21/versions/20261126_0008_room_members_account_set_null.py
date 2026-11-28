"""Allow room_members.account_id NULL on account delete (SET NULL).

Revision ID: 20261126_0008
Revises: 20261121_0007
Create Date: 2026-11-26

- room_members.account_id: NOT NULL + ON DELETE RESTRICT
  → nullable + ON DELETE SET NULL (anonymize leavers; keep rooms/other members)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20261126_0008"
down_revision: Union[str, Sequence[str], None] = "20261121_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "fk_room_members_account_id"


def _account_fk_names(bind) -> list[str]:
    return [
        fk["name"]
        for fk in inspect(bind).get_foreign_keys("room_members")
        if fk.get("referred_table") == "accounts"
        and fk.get("constrained_columns") == ["account_id"]
        and fk.get("name")
    ]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # Unnamed FKs from 0001 cannot be dropped by name. Recreate makes account_id
        # nullable; ORM/create_all paths already use ON DELETE SET NULL. PostgreSQL
        # gets the full FK rewrite below. Application code also nulls account_id
        # before deleting accounts.
        with op.batch_alter_table("room_members", recreate="always") as batch:
            batch.alter_column(
                "account_id",
                existing_type=sa.String(length=36),
                nullable=True,
                existing_nullable=False,
            )
        return

    for name in _account_fk_names(bind) or ["room_members_account_id_fkey"]:
        op.drop_constraint(name, "room_members", type_="foreignkey")
    op.alter_column(
        "room_members",
        "account_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    op.create_foreign_key(
        _FK_NAME,
        "room_members",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    nulls = bind.execute(
        sa.text("SELECT COUNT(*) FROM room_members WHERE account_id IS NULL")
    ).scalar()
    if nulls:
        raise RuntimeError(
            "Cannot restore RESTRICT/NOT NULL on room_members.account_id: "
            f"{nulls} row(s) have account_id NULL. Re-link or remove them first."
        )

    if dialect == "sqlite":
        with op.batch_alter_table("room_members", recreate="always") as batch:
            batch.alter_column(
                "account_id",
                existing_type=sa.String(length=36),
                nullable=False,
                existing_nullable=True,
            )
        return

    op.drop_constraint(_FK_NAME, "room_members", type_="foreignkey")
    op.alter_column(
        "room_members",
        "account_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.create_foreign_key(
        "room_members_account_id_fkey",
        "room_members",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
