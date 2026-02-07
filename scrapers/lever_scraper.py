import logging

from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from scrapers.utils import normalize_url

logger = logging.getLogger(__name__)


class LeverScraper(BaseScraper):
    """Scraper for Lever ATS job boards (jobs.lever.co)."""

    async def extract_jobs(self, page: Page) -> list[dict]:
        jobs = []

        # Lever standard structure
        postings = await page.query_selector_all(".posting")

        if not postings:
            # Try alternate selectors
            postings = await page.query_selector_all('[data-qa="posting-name"]')

        if not postings:
            # Fallback
            links = await page.query_selector_all('a[href*="/jobs/"], a[href*="/apply"]')
            for link in links:
                try:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if title and href and len(title) > 3:
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

        for posting in postings:
            try:
                # Title
                title_el = await posting.query_selector("h5, .posting-name, [data-qa='posting-name']")
                if not title_el:
                    title_el = await posting.query_selector("a")
                if not title_el:
                    continue

                title = (await title_el.inner_text()).strip()

                # URL
                link_el = await posting.query_selector("a.posting-title, a[href]")
                href = await link_el.get_attribute("href") if link_el else None
                if not href:
                    href = await posting.evaluate("el => { const a = el.querySelector('a'); return a ? a.href : ''; }")

                if not title or not href:
                    continue

                # Location
                location_el = await posting.query_selector(
                    ".posting-categories .location, .sort-by-location, span.workplaceTypes"
                )
                location = (await location_el.inner_text()).strip() if location_el else ""

                # Team/Department
                team_el = await posting.query_selector(".posting-categories .department, .sort-by-team")
                team = (await team_el.inner_text()).strip() if team_el else ""

                # Commitment (Full-time, Part-time)
                commitment_el = await posting.query_selector(".posting-categories .commitment")
                commitment = (await commitment_el.inner_text()).strip() if commitment_el else ""

                description_parts = [p for p in [team, commitment] if p]

                jobs.append({
                    "title": title,
                    "company": "",
                    "location": location,
                    "url": normalize_url(href, self.base_url),
                    "salary": "",
                    "posted_date": None,
                    "description": " | ".join(description_parts),
                })

            except Exception:
                logger.debug("Failed to extract Lever posting", exc_info=True)
                continue

        # Extract company name from header
        company_el = await page.query_selector(".main-header-title h1, .company-name")
        company_name = (await company_el.inner_text()).strip() if company_el else ""
        if company_name:
            for job in jobs:
                job["company"] = company_name

        return jobs

    async def go_to_next_page(self, page: Page) -> bool:
        # Lever typically shows all positions on one page
        return False
