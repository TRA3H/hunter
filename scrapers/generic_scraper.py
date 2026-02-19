import logging

from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from scrapers.utils import normalize_url, random_delay

logger = logging.getLogger(__name__)

# Default CSS selectors — users can override these via scraper_config
DEFAULT_SELECTORS = {
    "job_card": ".job-card, .job-listing, .job-item, .posting, [data-job], .job-result, .result-card",
    "title": "h2 a, h3 a, .job-title a, .title a, [data-job-title], .posting-title",
    "company": ".company, .company-name, .employer, [data-company], .posting-company",
    "location": ".location, .job-location, [data-location], .posting-location",
    "link": "a[href]",
    "salary": ".salary, .compensation, .pay, [data-salary]",
    "posted_date": ".date, .posted, .posted-date, time, [datetime]",
    "description": ".description, .job-description, .summary, .snippet",
    "next_page": ".next, .pagination .next, a[rel='next'], .load-more, button:has-text('Next')",
}


class GenericScraper(BaseScraper):
    """Generic scraper that uses configurable CSS selectors to extract job data."""

    def __init__(self, base_url: str, config: dict | None = None):
        super().__init__(base_url, config)
        self.selectors = {**DEFAULT_SELECTORS, **(self.config.get("selectors") or {})}
        self.pagination_type = self.config.get("pagination_type", "click")
        self._current_page = 1
        self._url_page_param = self.config.get("url_page_param", "page")

    async def extract_jobs(self, page: Page) -> list[dict]:
        jobs = []

        # Find job cards
        cards = await page.query_selector_all(self.selectors["job_card"])
        if not cards:
            logger.warning("No job cards found with selector: %s", self.selectors["job_card"])
            # Fallback: try to find any links that look like job listings
            cards = await page.query_selector_all("a[href*='job'], a[href*='position'], a[href*='career']")

        logger.info("Found %d potential job cards", len(cards))

        for card in cards:
            try:
                job = await self._extract_single_job(card, page)
                if job and job.get("title") and job.get("url"):
                    jobs.append(job)
            except Exception:
                logger.debug("Failed to extract job from card", exc_info=True)
                continue

        return jobs

    async def _extract_single_job(self, card, page: Page) -> dict | None:
        """Extract job data from a single card element."""
        job = {}

        # Title
        title_el = await card.query_selector(self.selectors["title"])
        if title_el:
            job["title"] = (await title_el.inner_text()).strip()
        else:
            # Try the card itself
            text = await card.inner_text()
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
            job["title"] = lines[0] if lines else ""

        # URL
        link_el = await card.query_selector(self.selectors["link"])
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                job["url"] = normalize_url(href, self.base_url)
        elif title_el:
            href = await title_el.get_attribute("href")
            if href:
                job["url"] = normalize_url(href, self.base_url)

        if not job.get("url"):
            href = await card.get_attribute("href")
            if href:
                job["url"] = normalize_url(href, self.base_url)

        # Company
        company_el = await card.query_selector(self.selectors["company"])
        job["company"] = (await company_el.inner_text()).strip() if company_el else ""

        # Location
        location_el = await card.query_selector(self.selectors["location"])
        job["location"] = (await location_el.inner_text()).strip() if location_el else ""

        # Salary
        salary_el = await card.query_selector(self.selectors["salary"])
        job["salary"] = (await salary_el.inner_text()).strip() if salary_el else ""

        # Posted date
        date_el = await card.query_selector(self.selectors["posted_date"])
        if date_el:
            date_attr = await date_el.get_attribute("datetime")
            job["posted_date"] = date_attr or (await date_el.inner_text()).strip()
        else:
            job["posted_date"] = None

        # Description snippet
        desc_el = await card.query_selector(self.selectors["description"])
        job["description"] = (await desc_el.inner_text()).strip() if desc_el else ""

        return job

    async def go_to_next_page(self, page: Page) -> bool:
        if self.pagination_type == "click":
            return await self._paginate_click(page)
        elif self.pagination_type == "infinite_scroll":
            return await self._paginate_scroll(page)
        elif self.pagination_type == "url_param":
            return await self._paginate_url(page)
        return False

    async def _paginate_click(self, page: Page) -> bool:
        """Click a 'Next' button for pagination."""
        try:
            next_btn = await page.query_selector(self.selectors["next_page"])
            if not next_btn:
                return False

            is_disabled = await next_btn.get_attribute("disabled")
            if is_disabled is not None:
                return False

            classes = await next_btn.get_attribute("class") or ""
            if "disabled" in classes:
                return False

            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            await random_delay()
            return True
        except Exception:
            logger.debug("No next page found")
            return False

    async def _paginate_scroll(self, page: Page) -> bool:
        """Scroll down to load more results (infinite scroll)."""
        try:
            prev_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await random_delay(2.0, 4.0)
            new_height = await page.evaluate("document.body.scrollHeight")
            return new_height > prev_height
        except Exception:
            return False

    async def _paginate_url(self, page: Page) -> bool:
        """URL parameter-based pagination."""
        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

            self._current_page += 1
            parsed = urlparse(self.base_url)
            params = parse_qs(parsed.query)
            params[self._url_page_param] = [str(self._current_page)]
            new_query = urlencode(params, doseq=True)
            next_url = urlunparse(parsed._replace(query=new_query))

            await page.goto(next_url, wait_until="networkidle", timeout=15000)
            await random_delay()
            return True
        except Exception:
            logger.debug("URL pagination failed")
            return False
