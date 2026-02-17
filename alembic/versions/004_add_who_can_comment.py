"""Add who_can_comment to users for comment privacy.

Revision ID: 004
Revises: 003
Create Date: 2024-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("who_can_comment", sa.String(30), nullable=False, server_default="everyone"))


def downgrade() -> None:
    op.drop_column("users", "who_can_comment")
