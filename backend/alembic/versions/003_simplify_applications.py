"""Simplify applications model: add notes/applied_via, drop auto-apply columns

Revision ID: 003
Revises: 002
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns
    op.add_column("applications", sa.Column("notes", sa.Text, server_default="", nullable=False))
    op.add_column("applications", sa.Column("applied_via", sa.String(100), server_default="manual", nullable=False))

    # Map old status values to new ones
    op.execute("""
        UPDATE applications SET status = 'applied'
        WHERE status IN ('pending', 'in_progress', 'needs_review', 'ready_to_submit')
    """)
    op.execute("""
        UPDATE applications SET status = 'withdrawn'
        WHERE status = 'cancelled'
    """)

    # Make job_id nullable
    op.alter_column("applications", "job_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # Drop old auto-apply columns
    op.drop_column("applications", "form_fields")
    op.drop_column("applications", "screenshot_path")
    op.drop_column("applications", "current_page_url")
    op.drop_column("applications", "ai_answers")
    op.drop_column("applications", "error_message")
    op.drop_column("applications", "celery_task_id")
    op.drop_column("applications", "submitted_at")

    # Drop screenshot_path from application_logs
    op.drop_column("application_logs", "screenshot_path")


def downgrade() -> None:
    # Re-add screenshot_path to application_logs
    op.add_column("application_logs", sa.Column("screenshot_path", sa.Text, server_default=""))

    # Re-add old columns to applications
    op.add_column("applications", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("celery_task_id", sa.String(255), server_default=""))
    op.add_column("applications", sa.Column("error_message", sa.Text, server_default=""))
    op.add_column("applications", sa.Column("ai_answers", postgresql.JSONB, nullable=True))
    op.add_column("applications", sa.Column("current_page_url", sa.Text, server_default=""))
    op.add_column("applications", sa.Column("screenshot_path", sa.Text, server_default=""))
    op.add_column("applications", sa.Column("form_fields", postgresql.JSONB, nullable=True))

    # Make job_id NOT NULL again
    op.alter_column("applications", "job_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    # Drop new columns
    op.drop_column("applications", "applied_via")
    op.drop_column("applications", "notes")
