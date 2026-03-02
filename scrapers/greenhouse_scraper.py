import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from scrapers.utils import get_random_user_agent

logger = logging.getLogger(__name__)

# Greenhouse public API: https://developers.greenhouse.io/job-board.html
API_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _extract_token(url: str) -> str | None:
    """Extract the board token from a Greenhouse URL.

    Supports:
      - boards.greenhouse.io/company
      - boards.greenhouse.io/company/jobs
      - company.greenhouse.io
      - job-boards.greenhouse.io/company
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "greenhouse.io" not in host:
        return None

    # boards.greenhouse.io/TOKEN or job-boards.greenhouse.io/TOKEN
    if host.startswith("boards.") or host.startswith("job-boards."):
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return parts[0]

    # TOKEN.greenhouse.io (custom subdomain)
    subdomain = host.split(".")[0]
    if subdomain not in ("boards", "job-boards", "www"):
        return subdomain

    return None


class GreenhouseScraper:
    """Scraper for Greenhouse ATS using their free public REST API.

    No browser needed — uses boards-api.greenhouse.io/v1/boards/{token}/jobs.
    """

    def __init__(self, base_url: str, config: dict[str, Any] | None = None):
        self.base_url = base_url
        self.config = config or {}
        self.token = self.config.get("board_token") or _extract_token(base_url)

    async def scrape(self) -> list[dict]:
        if not self.token:
            logger.error("Could not extract Greenhouse board token from %s", self.base_url)
            return []

        api_url = API_BASE.format(token=self.token)
        jobs = []

        async with httpx.AsyncClient(timeout=30) as client:
            params = {"content": "true"}
            response = await client.get(
                api_url,
                params=params,
                headers={"User-Agent": get_random_user_agent()},
            )
            response.raise_for_status()
            data = response.json()

        for posting in data.get("jobs", []):
            title = posting.get("title", "").strip()
            if not title:
                continue

            # Location can be a single object or nested
            location_obj = posting.get("location", {})
            location = location_obj.get("name", "") if isinstance(location_obj, dict) else str(location_obj)

            # Build absolute URL
            job_url = posting.get("absolute_url", "")
            if not job_url:
                job_id = posting.get("id", "")
                job_url = f"https://boards.greenhouse.io/{self.token}/jobs/{job_id}"

            # Strip HTML from content for description
            content = posting.get("content", "")
            description = re.sub(r"<[^>]+>", " ", content).strip()
            description = re.sub(r"\s+", " ", description)[:2000]

            # Departments as extra info
            departments = [d.get("name", "") for d in posting.get("departments", [])]

            jobs.append({
                "title": title,
                "company": "",  # Filled by scan_tasks from board name
                "location": location,
                "url": job_url,
                "salary": "",
                "posted_date": posting.get("updated_at"),
                "description": description,
            })

        logger.info("Greenhouse API returned %d jobs for token '%s'", len(jobs), self.token)
        return jobs
