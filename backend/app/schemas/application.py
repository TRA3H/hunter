import uuid
from datetime import datetime

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID | None = None
    status: str = "applied"
    notes: str = ""
    applied_via: str = "manual"


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class ApplicationLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    details: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None = None
    status: str
    notes: str
    applied_via: str
    created_at: datetime
    updated_at: datetime
    logs: list[ApplicationLogResponse] = []
    job_title: str | None = None
    job_company: str | None = None
    job_url: str | None = None
    match_score: int | None = None

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


class DashboardStats(BaseModel):
    active_boards: int
    total_jobs: int
    new_jobs: int
    total_applications: int
    applications_by_status: dict[str, int]
    jobs_by_board: list[dict]
    applications_over_time: list[dict]
    recent_activity: list[dict]
