import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobBoard(Base):
    __tablename__ = "job_boards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    scan_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    keyword_filters: Mapped[list] = mapped_column(JSONB, default=list)
    scraper_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # scraper_config can include:
    #   scraper_type: "generic" | "workday" | "greenhouse" | "lever"
    #   selectors: { job_card, title, company, location, link, next_page }
    #   pagination_type: "click" | "url_param" | "infinite_scroll"
    #   max_pages: int
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scan_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # success, error, running
    last_scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs_found_last_scan: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="board", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<JobBoard {self.name} ({self.url})>"
