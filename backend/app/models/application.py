import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"  # Paused, waiting for human input
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=ApplicationStatus.PENDING)

    # Form state when paused for review
    form_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structure: [{ field_name, field_type, label, value, confidence, status: "filled"|"needs_input", options? }]
    screenshot_path: Mapped[str] = mapped_column(Text, default="")
    current_page_url: Mapped[str] = mapped_column(Text, default="")

    # AI-generated answers (user reviews before submit)
    ai_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str] = mapped_column(Text, default="")
    celery_task_id: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    logs: Mapped[list["ApplicationLog"]] = relationship("ApplicationLog", back_populates="application", cascade="all, delete-orphan")


class ApplicationLog(Base):
    __tablename__ = "application_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")
    screenshot_path: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped["Application"] = relationship("Application", back_populates="logs")
