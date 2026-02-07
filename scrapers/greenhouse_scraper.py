import logging

from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from scrapers.utils import normalize_url

logger = logging.getLogger(__name__)


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse ATS job boards (boards.greenhouse.io)."""

    async def extract_jobs(self, page: Page) -> list[dict]:
        jobs = []

        # Greenhouse uses a standard structure
        sections = await page.query_selector_all("section.level-0, .opening")

        if not sections:
            # Try the newer Greenhouse layout
            sections = await page.query_selector_all("[data-mapped='true'] .opening, .job-post")

        if not sections:
            # Fallback: look for links with /jobs/ in href
            links = await page.query_selector_all('a[href*="/jobs/"]')
            for link in links:
                try:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if title and href:
                        jobs.append({
                            "title": title,
                            "company": "",
                            "location": "",
                            "url": normalize_url(href, self.base_url),
                            "salary": "",
                            "posted_date": None,
                            "description": "",
                        })
                except Exception:
                    continue
            return jobs

        for section in sections:
            try:
                # Title and link
                link_el = await section.query_selector("a")
                if not link_el:
                    continue

                title = (await link_el.inner_text()).strip()
                href = await link_el.get_attribute("href")

                if not title or not href:
                    continue

                # Location
                location_el = await section.query_selector(".location, span:last-child")
                location = (await location_el.inner_text()).strip() if location_el else ""

                jobs.append({
                    "title": title,
                    "company": "",  # Usually company is in the page header
                    "location": location,
                    "url": normalize_url(href, self.base_url),
                    "salary": "",
                    "posted_date": None,
                    "description": "",
                })

            except Exception:
                logger.debug("Failed to extract Greenhouse job", exc_info=True)
                continue

        # Try to extract company name from page header
        company_el = await page.query_selector("h1, .company-name, [data-company]")
        company_name = (await company_el.inner_text()).strip() if company_el else ""
        if company_name:
            for job in jobs:
                job["company"] = company_name

        return jobs

    async def go_to_next_page(self, page: Page) -> bool:
        # Greenhouse typically shows all jobs on one page
        return False
