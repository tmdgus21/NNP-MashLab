"""Add accounts.nickname and drop room_members nickname uniqueness.

Revision ID: 20261121_0007
Revises: 20261120_0006
Create Date: 2026-11-21

- accounts.nickname VARCHAR(30) NOT NULL after backfill (duplicates allowed)
- drop uq_room_members_room_nickname so same display names can coexist per room
- downgrade refuses to restore UNIQUE if duplicate (room_id, nickname) rows exist
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261121_0007"
down_revision: Union[str, Sequence[str], None] = "20261120_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic-enough backfill tokens (migration-time only; runtime uses nickname_generator).
_ADJECTIVES = (
    "행복한",
    "졸린",
    "용감한",
    "신나는",
    "귀여운",
    "차분한",
    "씩씩한",
    "포근한",
    "반짝이는",
    "상큼한",
)
_FOODS = (
    "감자",
    "고구마",
    "만두",
    "푸딩",
    "김밥",
    "떡볶이",
    "라면",
    "비빔밥",
    "호빵",
    "붕어빵",
)


def _backfill_nickname(account_id: str, index: int) -> str:
    adj = _ADJECTIVES[index % len(_ADJECTIVES)]
    food = _FOODS[(index // len(_ADJECTIVES)) % len(_FOODS)]
    # Stable 3-digit from account id hash for uniqueness-ish backfill labels.
    n = (sum(ord(c) for c in account_id) + index) % 900 + 100
    name = f"{adj}{food}{n}"
    return name[:30]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.add_column("accounts", sa.Column("nickname", sa.String(length=30), nullable=True))

    rows = bind.execute(sa.text("SELECT id FROM accounts")).fetchall()
    for i, (account_id,) in enumerate(rows):
        nick = _backfill_nickname(account_id, i)
        bind.execute(
            sa.text("UPDATE accounts SET nickname = :n WHERE id = :id"),
            {"n": nick, "id": account_id},
        )

    if dialect == "sqlite":
        with op.batch_alter_table("accounts") as batch:
            batch.alter_column(
                "nickname",
                existing_type=sa.String(length=30),
                nullable=False,
            )
        with op.batch_alter_table("room_members") as batch:
            batch.drop_constraint("uq_room_members_room_nickname", type_="unique")
    else:
        op.alter_column(
            "accounts",
            "nickname",
            existing_type=sa.String(length=30),
            nullable=False,
        )
        op.drop_constraint(
            "uq_room_members_room_nickname",
            "room_members",
            type_="unique",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    dups = bind.execute(
        sa.text(
            """
            SELECT room_id, nickname, COUNT(*) AS c
            FROM room_members
            GROUP BY room_id, nickname
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dups:
        raise RuntimeError(
            "Cannot restore uq_room_members_room_nickname: "
            f"{len(dups)} duplicate (room_id, nickname) group(s) exist. "
            "Resolve duplicates before downgrade."
        )

    if dialect == "sqlite":
        with op.batch_alter_table("room_members") as batch:
            batch.create_unique_constraint(
                "uq_room_members_room_nickname",
                ["room_id", "nickname"],
            )
        with op.batch_alter_table("accounts") as batch:
            batch.drop_column("nickname")
    else:
        op.create_unique_constraint(
            "uq_room_members_room_nickname",
            "room_members",
            ["room_id", "nickname"],
        )
        op.drop_column("accounts", "nickname")
