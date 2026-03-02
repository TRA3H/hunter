import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class PreSearchAction(BaseModel):
    action: str  # fill, click, wait, scroll, select, press, delay
    selector: str = ""
    value: str = ""
    state: str = ""  # For wait action: networkidle, selector
    wait_selector: str = ""
    key: str = ""  # For press action
    times: int = 3  # For scroll action
    timeout: int = 10000  # For wait action
    ms: int = 2000  # For delay action
    direction: str = "bottom"  # For scroll action


class ScraperConfig(BaseModel):
    scraper_type: str = "generic"  # auto, generic, workday, greenhouse, lever, interactive
    selectors: dict[str, str] = {}
    pagination_type: str = "click"  # click, url_param, infinite_scroll
    max_pages: int = 5
    pre_search_actions: list[PreSearchAction] = []
    intercept_patterns: list[str] = []
    intercept_job_path: str = ""
    intercept_title_key: str = "title"
    intercept_location_key: str = "location"
    intercept_url_key: str = "url"


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
