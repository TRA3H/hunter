import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from scrapers.utils import get_random_user_agent

logger = logging.getLogger(__name__)


def _extract_workday_parts(url: str) -> tuple[str, str] | None:
    """Extract (company, site) from a Workday URL.

    Supports:
      - company.wd5.myworkdayjobs.com/en-US/External
      - company.wd1.myworkdayjobs.com/External
      - myworkdayjobs.com/en-US/company/External
    Returns (tenant, site_id) for the CXS API.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    if "myworkdayjobs.com" not in host:
        return None

    # Subdomain pattern: company.wd5.myworkdayjobs.com
    subdomain = host.split(".")[0]

    # Filter out locale segments like "en-US", "fr-FR"
    path_parts = [p for p in path_parts if not re.match(r"^[a-z]{2}-[A-Z]{2}$", p)]

    if subdomain and subdomain != "www" and not subdomain.startswith("wd"):
        # company.wdN.myworkdayjobs.com/SiteId
        tenant = subdomain
        site_id = path_parts[0] if path_parts else "External"
        return (tenant, site_id)

    # Fallback: try to get from path
    if len(path_parts) >= 2:
        return (path_parts[0], path_parts[1])
    if len(path_parts) == 1:
        return (path_parts[0], "External")

    return None


class WorkdayScraper:
    """Scraper for Workday ATS using the hidden CXS POST API.

    No browser needed — uses POST to {base}/wday/cxs/{tenant}/{site}/jobs.
    """

    def __init__(self, base_url: str, config: dict[str, Any] | None = None):
        self.base_url = base_url
        self.config = config or {}
        self.max_jobs = self.config.get("max_jobs", 200)

        # Allow explicit config override
        if self.config.get("workday_tenant") and self.config.get("workday_site"):
            self._tenant = self.config["workday_tenant"]
            self._site = self.config["workday_site"]
        else:
            parts = _extract_workday_parts(base_url)
            if parts:
                self._tenant, self._site = parts
            else:
                self._tenant = self._site = None

    def _build_api_url(self) -> str:
        """Build the CXS API endpoint URL."""
        parsed = urlparse(self.base_url)
        # Reconstruct the base host (e.g. company.wd5.myworkdayjobs.com)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return f"{base}/wday/cxs/{self._tenant}/{self._site}/jobs"

    async def scrape(self) -> list[dict]:
        if not self._tenant or not self._site:
            logger.error("Could not extract Workday tenant/site from %s", self.base_url)
            return []

        api_url = self._build_api_url()
        all_jobs = []
        offset = 0
        limit = 20  # Workday API default page size

        headers = {
            "Content-Type": "application/json",
            "User-Agent": get_random_user_agent(),
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            while offset < self.max_jobs:
                payload = {
                    "appliedFacets": {},
                    "limit": limit,
                    "offset": offset,
                    "searchText": "",
                }

                # Add keyword search if configured
                search_text = self.config.get("search_text", "")
                if search_text:
                    payload["searchText"] = search_text

                try:
                    response = await client.post(
                        api_url,
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error("Workday API error %s for %s: %s", e.response.status_code, api_url, e)
                    break
                except Exception as e:
                    logger.error("Workday API request failed for %s: %s", api_url, e)
                    break

                job_postings = data.get("jobPostings", [])
                if not job_postings:
                    break

                parsed_base = urlparse(self.base_url)
                base_host = f"{parsed_base.scheme}://{parsed_base.netloc}"

                for posting in job_postings:
                    title = posting.get("title", "").strip()
                    if not title:
                        continue

                    # Build job URL from external path
                    external_path = posting.get("externalPath", "")
                    if external_path:
                        job_url = f"{base_host}{external_path}"
                    else:
                        job_url = posting.get("absoluteUrl", self.base_url)

                    # Location can be in bulletFields or locationsText
                    location = ""
                    for field in posting.get("bulletFields", []):
                        if isinstance(field, str) and not field.startswith("posted"):
                            location = field
                            break
                    if not location:
                        location = posting.get("locationsText", "")

                    # Posted date
                    posted_on = posting.get("postedOn", "")

                    all_jobs.append({
                        "title": title,
                        "company": "",  # Filled by scan_tasks from board name
                        "location": location,
                        "url": job_url,
                        "salary": "",
                        "posted_date": posted_on or None,
                        "description": "",
                    })

                total = data.get("total", 0)
                offset += limit
                if offset >= total:
                    break

        logger.info(
            "Workday API returned %d jobs for %s/%s",
            len(all_jobs), self._tenant, self._site,
        )
        return all_jobs
