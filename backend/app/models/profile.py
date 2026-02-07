import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    linkedin_url: Mapped[str] = mapped_column(Text, default="")
    website_url: Mapped[str] = mapped_column(Text, default="")

    # Standard EEO answers (all optional)
    us_citizen: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sponsorship_needed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    veteran_status: Mapped[str] = mapped_column(String(50), default="")  # "yes", "no", "prefer_not_to_say"
    disability_status: Mapped[str] = mapped_column(String(50), default="")
    gender: Mapped[str] = mapped_column(String(50), default="")
    ethnicity: Mapped[str] = mapped_column(String(100), default="")

    # Resume
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    resume_path: Mapped[str] = mapped_column(Text, default="")

    # Cover letter template
    cover_letter_template: Mapped[str] = mapped_column(Text, default="")

    # Preferences
    desired_title: Mapped[str] = mapped_column(String(255), default="")
    desired_locations: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    min_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_preference: Mapped[str] = mapped_column(String(50), default="")  # remote, hybrid, onsite, any

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    education: Mapped[list["Education"]] = relationship("Education", back_populates="profile", cascade="all, delete-orphan")
    work_experience: Mapped[list["WorkExperience"]] = relationship("WorkExperience", back_populates="profile", cascade="all, delete-orphan")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    school: Mapped[str] = mapped_column(String(255), default="")
    degree: Mapped[str] = mapped_column(String(100), default="")
    field_of_study: Mapped[str] = mapped_column(String(255), default="")
    gpa: Mapped[str] = mapped_column(String(10), default="")
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="education")


class WorkExperience(Base):
    __tablename__ = "work_experience"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")  # YYYY-MM format
    end_date: Mapped[str] = mapped_column(String(20), default="")  # YYYY-MM or "present"
    description: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="work_experience")
