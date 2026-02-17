"""Add follow_requests table for private profile follow requests.

Revision ID: 006
Revises: 005
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow_requests",
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("requester_id", "target_id"),
        sa.UniqueConstraint("requester_id", "target_id", name="uq_follow_requests_requester_target"),
    )
    op.create_index("ix_follow_requests_target_id", "follow_requests", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_follow_requests_target_id", table_name="follow_requests")
    op.drop_table("follow_requests")
