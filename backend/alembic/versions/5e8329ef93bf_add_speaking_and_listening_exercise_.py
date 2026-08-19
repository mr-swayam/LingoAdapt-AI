"""add speaking and listening exercise types

Revision ID: 5e8329ef93bf
Revises: 7a8142c4dff7
Create Date: 2026-08-17 20:50:36.973367

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5e8329ef93bf'
down_revision: str | None = '7a8142c4dff7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Autogenerate never detects enum value additions - must run outside the
    # migration's transaction (Postgres restriction on ALTER TYPE ... ADD VALUE).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE exercise_type ADD VALUE IF NOT EXISTS 'SPEAKING'")
        op.execute("ALTER TYPE exercise_type ADD VALUE IF NOT EXISTS 'LISTENING'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - an orphaned enum value is
    # harmless if unused after downgrade (same approach as the
    # CONVERSATION_CORRECTION migration before this one).
    pass
