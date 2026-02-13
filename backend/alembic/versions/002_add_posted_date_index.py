"""Add posted_date index for recency queries

Revision ID: 002
Revises: 001
Create Date: 2026-02-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_jobs_posted_date", "jobs", ["posted_date"])


def downgrade() -> None:
    op.drop_index("ix_jobs_posted_date", table_name="jobs")
