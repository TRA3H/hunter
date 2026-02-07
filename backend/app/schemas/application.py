import uuid
from datetime import datetime

from pydantic import BaseModel


class FormField(BaseModel):
    field_name: str
    field_type: str  # text, textarea, select, checkbox, radio, file
    label: str
    value: str = ""
    confidence: float = 0.0
    status: str = "needs_input"  # filled, needs_input
    options: list[str] = []


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class ApplicationReview(BaseModel):
    form_fields: list[FormField]


class ApplicationLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    details: str
    screenshot_path: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    form_fields: list[FormField] | None = None
    screenshot_path: str
    current_page_url: str
    ai_answers: dict | None = None
    error_message: str
    celery_task_id: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None
    logs: list[ApplicationLogResponse] = []
    job_title: str | None = None
    job_company: str | None = None

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int


class DashboardStats(BaseModel):
    active_boards: int
    total_jobs: int
    new_jobs: int
    in_progress_applications: int
    needs_review_applications: int
    submitted_applications: int
    total_applications: int
    jobs_by_board: list[dict]
    applications_over_time: list[dict]
    recent_activity: list[dict]
