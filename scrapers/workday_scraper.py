import logging

from playwright.async_api import Page

from scrapers.base_scraper import BaseScraper
from scrapers.utils import normalize_url, random_delay

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseScraper):
    """Scraper for Workday ATS job boards (myworkdayjobs.com, wd5.myworkdayjobs.com, etc).

    Workday sites are heavily JavaScript-rendered, so we rely on Playwright
    to wait for dynamic content.
    """

    async def extract_jobs(self, page: Page) -> list[dict]:
        jobs = []

        # Wait for job listings to load (Workday is slow)
        try:
            await page.wait_for_selector(
                '[data-automation-id="jobResults"], .css-1q2dra3, section[data-automation-id="jobResults"]',
                timeout=15000,
            )
        except Exception:
            logger.warning("Workday job results container not found, trying fallback selectors")

        await random_delay(1.0, 2.0)

        # Try multiple selector strategies for Workday
        job_cards = await page.query_selector_all(
            '[data-automation-id="jobTitle"], '
            'a[data-automation-id="jobTitle"], '
            '.css-19uc56f, '
            'li[class*="css-"] a[href*="/job/"]'
        )

        if not job_cards:
            # Broader fallback
            job_cards = await page.query_selector_all('a[href*="/job/"]')

        for card in job_cards:
            try:
                tag = await card.evaluate("el => el.tagName.toLowerCase()")

                if tag == "a":
                    title = (await card.inner_text()).strip()
                    href = await card.get_attribute("href")
                else:
                    title = (await card.inner_text()).strip()
                    link = await card.query_selector("a")
                    href = await link.get_attribute("href") if link else None

                if not title or not href:
                    continue

                # Try to find sibling/parent elements for location and other data
                parent = await card.evaluate(
                    """el => {
                        let p = el.closest('li') || el.parentElement?.parentElement;
                        if (!p) return {};
                        let texts = Array.from(p.querySelectorAll('dd, [data-automation-id="locations"], .css-129m7dg'))
                            .map(e => e.textContent.trim());
                        return { texts };
                    }"""
                )

                texts = parent.get("texts", []) if parent else []
                location = texts[0] if texts else ""

                jobs.append({
                    "title": title,
                    "company": "",
                    "location": location,
                    "url": normalize_url(href, self.base_url),
                    "salary": "",
                    "posted_date": None,
                    "description": "",
                })

            except Exception:
                logger.debug("Failed to extract Workday job card", exc_info=True)
                continue

        # Try to extract company name
        company_el = await page.query_selector(
            '[data-automation-id="orgName"], .css-1oyvp5d, header h1'
        )
        company_name = (await company_el.inner_text()).strip() if company_el else ""
        if company_name:
            for job in jobs:
                job["company"] = company_name

        return jobs

    async def go_to_next_page(self, page: Page) -> bool:
        """Workday uses a 'Show More' button or pagination arrows."""
        try:
            # Try 'Show More' / 'View More' button first
            show_more = await page.query_selector(
                'button[data-automation-id="loadMoreButton"], '
                'button:has-text("Show More"), '
                'button:has-text("View More")'
            )
            if show_more:
                is_disabled = await show_more.get_attribute("disabled")
                if is_disabled is None:
                    await show_more.click()
                    await page.wait_for_timeout(3000)
                    return True

            # Try next page arrow
            next_btn = await page.query_selector(
                'button[data-automation-id="next"], '
                'button[aria-label="next"], '
                'button:has-text("Next")'
            )
            if next_btn:
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled is None:
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    return True

            return False
        except Exception:
            logger.debug("Workday pagination failed")
            return False
