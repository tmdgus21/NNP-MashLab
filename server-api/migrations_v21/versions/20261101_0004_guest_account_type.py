"""Allow account_type=GUEST for disposable meeting participants.

Revision ID: 20261101_0004
Revises: 20261101_0003
Create Date: 2026-11-02

Email USER signup remains separate; guests must not be account_type=USER.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0004"
down_revision: Union[str, Sequence[str], None] = "20261101_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CHECK = "account_type IN ('USER', 'ADMIN', 'GUEST')"
OLD_CHECK = "account_type IN ('USER', 'ADMIN')"


def _dialect() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    dialect = _dialect()
    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_account_type"))
        op.execute(sa.text(f"ALTER TABLE accounts ADD CONSTRAINT ck_accounts_account_type CHECK ({NEW_CHECK})"))
    elif dialect == "sqlite":
        with op.batch_alter_table("accounts") as batch:
            batch.drop_constraint("ck_accounts_account_type", type_="check")
            batch.create_check_constraint("ck_accounts_account_type", NEW_CHECK)
    else:
        raise NotImplementedError(f"migration 20261101_0004 unsupported dialect: {dialect}")


def downgrade() -> None:
    dialect = _dialect()
    # Guests must be removed or retyped before restoring the narrower CHECK.
    op.execute(sa.text("UPDATE accounts SET account_type = 'USER' WHERE account_type = 'GUEST'"))
    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_account_type"))
        op.execute(sa.text(f"ALTER TABLE accounts ADD CONSTRAINT ck_accounts_account_type CHECK ({OLD_CHECK})"))
    elif dialect == "sqlite":
        with op.batch_alter_table("accounts") as batch:
            batch.drop_constraint("ck_accounts_account_type", type_="check")
            batch.create_check_constraint("ck_accounts_account_type", OLD_CHECK)
    else:
        raise NotImplementedError(f"migration 20261101_0004 unsupported dialect: {dialect}")
