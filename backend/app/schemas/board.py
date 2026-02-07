import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ScraperConfig(BaseModel):
    scraper_type: str = "generic"  # generic, workday, greenhouse, lever
    selectors: dict[str, str] = {}
    pagination_type: str = "click"  # click, url_param, infinite_scroll
    max_pages: int = 5


class BoardCreate(BaseModel):
    name: str
    url: str
    scan_interval_minutes: int = 60
    enabled: bool = True
    keyword_filters: list[str] = []
    scraper_config: ScraperConfig = ScraperConfig()


class BoardUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    scan_interval_minutes: int | None = None
    enabled: bool | None = None
    keyword_filters: list[str] | None = None
    scraper_config: ScraperConfig | None = None


class BoardResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    scan_interval_minutes: int
    enabled: bool
    keyword_filters: list
    scraper_config: dict
    last_scanned_at: datetime | None
    last_scan_status: str | None
    last_scan_error: str | None
    jobs_found_last_scan: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BoardListResponse(BaseModel):
    boards: list[BoardResponse]
    total: int
