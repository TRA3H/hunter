import uuid
from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    title: str
    company: str
    location: str
    url: str
    posted_date: datetime | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    description: str
    match_score: float
    is_new: bool
    is_hidden: bool
    created_at: datetime
    updated_at: datetime
    board_name: str | None = None
    application_status: str | None = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobFilters(BaseModel):
    search: str | None = None
    board_id: uuid.UUID | None = None
    min_score: float | None = None
    max_score: float | None = None
    location: str | None = None
    is_new: bool | None = None
    is_hidden: bool | None = None
    sort_by: str = "created_at"  # created_at, match_score, title, company
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 25
