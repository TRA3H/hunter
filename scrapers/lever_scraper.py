import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from scrapers.utils import get_random_user_agent

logger = logging.getLogger(__name__)

# Lever public API: https://github.com/lever/postings-api
API_BASE = "https://api.lever.co/v0/postings/{site}"


def _extract_site(url: str) -> str | None:
    """Extract the site slug from a Lever URL.

    Supports:
      - jobs.lever.co/company
      - jobs.lever.co/company/postings
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "lever.co" not in host:
        return None

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if parts:
        return parts[0]

    return None


class LeverScraper:
    """Scraper for Lever ATS using their free public REST API.

    No browser needed — uses api.lever.co/v0/postings/{site}?mode=json.
    """

    def __init__(self, base_url: str, config: dict[str, Any] | None = None):
        self.base_url = base_url
        self.config = config or {}
        self.site = self.config.get("site_slug") or _extract_site(base_url)

    async def scrape(self) -> list[dict]:
        if not self.site:
            logger.error("Could not extract Lever site slug from %s", self.base_url)
            return []

        api_url = API_BASE.format(site=self.site)
        jobs = []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                api_url,
                params={"mode": "json"},
                headers={"User-Agent": get_random_user_agent()},
            )
            response.raise_for_status()
            postings = response.json()

        if not isinstance(postings, list):
            logger.warning("Unexpected Lever API response type: %s", type(postings))
            return []

        for posting in postings:
            title = posting.get("text", "").strip()
            if not title:
                continue

            categories = posting.get("categories", {})
            location = categories.get("location", "")
            team = categories.get("team", "")
            commitment = categories.get("commitment", "")

            description_parts = [p for p in [team, commitment] if p]
            description_plain = posting.get("descriptionPlain", "")[:2000]
            if description_plain:
                description_parts.append(description_plain)

            jobs.append({
                "title": title,
                "company": "",  # Filled by scan_tasks from board name
                "location": location,
                "url": posting.get("hostedUrl", posting.get("applyUrl", "")),
                "salary": "",
                "posted_date": None,  # Lever API doesn't expose post dates
                "description": " | ".join(description_parts) if description_parts else "",
            })

        logger.info("Lever API returned %d jobs for site '%s'", len(jobs), self.site)
        return jobs
