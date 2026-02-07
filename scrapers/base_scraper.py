import abc
import logging
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from scrapers.utils import check_robots_txt, get_random_user_agent, random_delay

logger = logging.getLogger(__name__)


class BaseScraper(abc.ABC):
    """Abstract base class for all job board scrapers."""

    def __init__(self, base_url: str, config: dict[str, Any] | None = None):
        self.base_url = base_url
        self.config = config or {}
        self.max_pages = self.config.get("max_pages", 5)

    async def scrape(self) -> list[dict]:
        """Main entry point: launch browser, check robots, scrape, return jobs."""
        # Check robots.txt
        allowed = await check_robots_txt(self.base_url)
        if not allowed:
            logger.warning("robots.txt disallows scraping %s, skipping", self.base_url)
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=get_random_user_agent(),
            )
            page = await context.new_page()

            try:
                all_jobs = []
                await random_delay(1.0, 3.0)

                await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                await random_delay()

                for page_num in range(self.max_pages):
                    logger.info("Scraping page %d of %s", page_num + 1, self.base_url)

                    jobs = await self.extract_jobs(page)
                    all_jobs.extend(jobs)

                    has_next = await self.go_to_next_page(page)
                    if not has_next:
                        break

                    await random_delay()

                logger.info("Total jobs scraped from %s: %d", self.base_url, len(all_jobs))
                return all_jobs

            except Exception:
                logger.exception("Scraping failed for %s", self.base_url)
                raise
            finally:
                await browser.close()

    @abc.abstractmethod
    async def extract_jobs(self, page: Page) -> list[dict]:
        """Extract job listings from the current page.

        Must return a list of dicts with keys:
            title, company, location, url, posted_date (optional),
            salary (optional), description
        """

    @abc.abstractmethod
    async def go_to_next_page(self, page: Page) -> bool:
        """Navigate to the next page of results.

        Returns True if navigation succeeded, False if no more pages.
        """
