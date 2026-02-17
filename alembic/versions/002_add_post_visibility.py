"""Add post visibility (public, private, followers_only).

Revision ID: 002
Revises: 001
Create Date: 2024-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("visibility", sa.String(20), nullable=True))
    op.execute("UPDATE posts SET visibility = 'public' WHERE visibility IS NULL")
    op.alter_column("posts", "visibility", nullable=False)


def downgrade() -> None:
    op.drop_column("posts", "visibility")
