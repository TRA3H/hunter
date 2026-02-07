"""Initial migration

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_boards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("scan_interval_minutes", sa.Integer, default=60),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("keyword_filters", postgresql.JSONB, default=[]),
        sa.Column("scraper_config", postgresql.JSONB, default={}),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scan_status", sa.String(50), nullable=True),
        sa.Column("last_scan_error", sa.Text, nullable=True),
        sa.Column("jobs_found_last_scan", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), default=""),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("posted_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salary_min", sa.Integer, nullable=True),
        sa.Column("salary_max", sa.Integer, nullable=True),
        sa.Column("salary_currency", sa.String(10), default="USD"),
        sa.Column("description", sa.Text, default=""),
        sa.Column("description_tsv", postgresql.TSVECTOR, nullable=True),
        sa.Column("match_score", sa.Float, default=0.0),
        sa.Column("is_new", sa.Boolean, default=True),
        sa.Column("is_hidden", sa.Boolean, default=False),
        sa.Column("dedup_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_description_tsv", "jobs", ["description_tsv"], postgresql_using="gin")
    op.create_index("ix_jobs_match_score", "jobs", ["match_score"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_board_id", "jobs", ["board_id"])

    # Trigger to auto-update tsvector
    op.execute("""
        CREATE OR REPLACE FUNCTION jobs_tsv_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.description_tsv := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.description, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_jobs_tsv
        BEFORE INSERT OR UPDATE OF title, description ON jobs
        FOR EACH ROW EXECUTE FUNCTION jobs_tsv_trigger();
    """)

    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(100), default=""),
        sa.Column("last_name", sa.String(100), default=""),
        sa.Column("email", sa.String(255), default=""),
        sa.Column("phone", sa.String(50), default=""),
        sa.Column("linkedin_url", sa.Text, default=""),
        sa.Column("website_url", sa.Text, default=""),
        sa.Column("us_citizen", sa.Boolean, nullable=True),
        sa.Column("sponsorship_needed", sa.Boolean, nullable=True),
        sa.Column("veteran_status", sa.String(50), default=""),
        sa.Column("disability_status", sa.String(50), default=""),
        sa.Column("gender", sa.String(50), default=""),
        sa.Column("ethnicity", sa.String(100), default=""),
        sa.Column("resume_filename", sa.String(255), default=""),
        sa.Column("resume_path", sa.Text, default=""),
        sa.Column("cover_letter_template", sa.Text, default=""),
        sa.Column("desired_title", sa.String(255), default=""),
        sa.Column("desired_locations", sa.Text, default=""),
        sa.Column("min_salary", sa.Integer, nullable=True),
        sa.Column("remote_preference", sa.String(50), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "education",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profiles.id"), nullable=False),
        sa.Column("school", sa.String(255), default=""),
        sa.Column("degree", sa.String(100), default=""),
        sa.Column("field_of_study", sa.String(255), default=""),
        sa.Column("gpa", sa.String(10), default=""),
        sa.Column("graduation_year", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "work_experience",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profiles.id"), nullable=False),
        sa.Column("company", sa.String(255), default=""),
        sa.Column("title", sa.String(255), default=""),
        sa.Column("start_date", sa.String(20), default=""),
        sa.Column("end_date", sa.String(20), default=""),
        sa.Column("description", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("form_fields", postgresql.JSONB, nullable=True),
        sa.Column("screenshot_path", sa.Text, default=""),
        sa.Column("current_page_url", sa.Text, default=""),
        sa.Column("ai_answers", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, default=""),
        sa.Column("celery_task_id", sa.String(255), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "application_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", sa.Text, default=""),
        sa.Column("screenshot_path", sa.Text, default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_jobs_tsv ON jobs")
    op.execute("DROP FUNCTION IF EXISTS jobs_tsv_trigger()")
    op.drop_table("application_logs")
    op.drop_table("applications")
    op.drop_table("work_experience")
    op.drop_table("education")
    op.drop_table("user_profiles")
    op.drop_table("jobs")
    op.drop_table("job_boards")
