import json
import logging
import os
from typing import Any

from playwright.async_api import Page, Route, async_playwright

from scrapers.utils import (
    check_robots_txt,
    get_random_user_agent,
    normalize_url,
    random_delay,
)

logger = logging.getLogger(__name__)


class InteractiveScraper:
    """Scraper for SPA sites that require user interaction before showing results.

    Executes a configurable sequence of actions (fill, click, wait, scroll, select)
    before extracting jobs. Optionally intercepts API responses for structured data.

    Config format:
        {
            "scraper_type": "interactive",
            "pre_search_actions": [
                {"action": "fill", "selector": "input[type='search']", "value": "software engineer"},
                {"action": "click", "selector": "button[type='submit']"},
                {"action": "wait", "state": "networkidle"},
                {"action": "scroll", "direction": "bottom", "times": 3},
                {"action": "select", "selector": "select#location", "value": "US"}
            ],
            "intercept_patterns": ["*/api/*", "*/positions*"],
            "intercept_job_path": "jobPostings",
            "intercept_title_key": "title",
            "intercept_location_key": "location",
            "intercept_url_key": "url",
            "selectors": {
                "job_card": ".job-card",
                "title": ".job-title",
                "location": ".job-location",
                "link": "a[href]",
                ...
            },
            "max_pages": 5,
            "pagination_type": "click",
        }
    """

    def __init__(self, base_url: str, config: dict[str, Any] | None = None):
        self.base_url = base_url
        self.config = config or {}
        self.max_pages = self.config.get("max_pages", 3)
        self.pre_search_actions = self.config.get("pre_search_actions", [])
        self.intercept_patterns = self.config.get("intercept_patterns", [])
        self.selectors = self.config.get("selectors", {})
        self._intercepted_data: list[dict] = []

    async def scrape(self) -> list[dict]:
        allowed = await check_robots_txt(self.base_url)
        if not allowed:
            logger.warning("robots.txt disallows scraping %s, skipping", self.base_url)
            return []

        async with async_playwright() as p:
            headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=get_random_user_agent(),
            )
            page = await context.new_page()

            try:
                # Set up API response interception if configured
                if self.intercept_patterns:
                    await self._setup_interception(page)

                await random_delay(1.0, 3.0)
                await page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(1.0, 2.0)

                # Execute pre-search actions
                await self._execute_actions(page)

                # Wait for results to appear
                await random_delay(2.0, 4.0)

                # Try intercepted API data first
                if self._intercepted_data:
                    jobs = self._parse_intercepted_jobs()
                    if jobs:
                        logger.info("Extracted %d jobs from intercepted API responses", len(jobs))
                        return jobs

                # Fall back to CSS selector extraction
                all_jobs = []
                for page_num in range(self.max_pages):
                    logger.info("Extracting page %d of %s", page_num + 1, self.base_url)
                    jobs = await self._extract_jobs_css(page)
                    all_jobs.extend(jobs)

                    has_next = await self._go_to_next_page(page)
                    if not has_next:
                        break
                    await random_delay(1.0, 3.0)

                logger.info("Total jobs scraped from %s: %d", self.base_url, len(all_jobs))
                return all_jobs

            except Exception:
                logger.exception("Interactive scraping failed for %s", self.base_url)
                raise
            finally:
                await page.close()
                await context.close()
                await browser.close()

    async def _setup_interception(self, page: Page):
        """Set up route interception to capture API responses."""

        async def handle_route(route: Route):
            response = await route.fetch()
            try:
                body = await response.body()
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    data = json.loads(body)
                    self._intercepted_data.append(data)
                    logger.debug("Intercepted JSON response from %s", route.request.url)
            except Exception:
                pass
            await route.fulfill(response=response)

        for pattern in self.intercept_patterns:
            await page.route(pattern, handle_route)

    async def _execute_actions(self, page: Page):
        """Execute the configured pre-search action sequence."""
        for i, action_config in enumerate(self.pre_search_actions):
            action = action_config.get("action", "")
            selector = action_config.get("selector", "")
            logger.debug("Executing action %d: %s", i + 1, action)

            try:
                if action == "fill":
                    value = action_config.get("value", "")
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.fill(selector, value)

                elif action == "click":
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.click(selector)

                elif action == "wait":
                    state = action_config.get("state", "networkidle")
                    timeout = action_config.get("timeout", 15000)
                    if state == "networkidle":
                        await page.wait_for_load_state("networkidle", timeout=timeout)
                    elif state == "selector":
                        wait_selector = action_config.get("wait_selector", selector)
                        await page.wait_for_selector(wait_selector, timeout=timeout)
                    else:
                        await page.wait_for_timeout(timeout)

                elif action == "scroll":
                    times = action_config.get("times", 3)
                    for _ in range(times):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await random_delay(1.0, 2.0)

                elif action == "select":
                    value = action_config.get("value", "")
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.select_option(selector, value)

                elif action == "press":
                    key = action_config.get("key", "Enter")
                    if selector:
                        await page.wait_for_selector(selector, timeout=10000)
                        await page.press(selector, key)
                    else:
                        await page.keyboard.press(key)

                elif action == "delay":
                    ms = action_config.get("ms", 2000)
                    await page.wait_for_timeout(ms)

                else:
                    logger.warning("Unknown action type: %s", action)

            except Exception as e:
                logger.warning("Action %d (%s) failed: %s", i + 1, action, e)
                # Continue with remaining actions — some failures are non-fatal

    def _parse_intercepted_jobs(self) -> list[dict]:
        """Parse jobs from intercepted API response data."""
        jobs = []
        job_path = self.config.get("intercept_job_path", "")
        title_key = self.config.get("intercept_title_key", "title")
        location_key = self.config.get("intercept_location_key", "location")
        url_key = self.config.get("intercept_url_key", "url")
        company_key = self.config.get("intercept_company_key", "company")
        description_key = self.config.get("intercept_description_key", "description")

        for data in self._intercepted_data:
            # Navigate to the job list within the response
            job_list = data
            if job_path:
                for key in job_path.split("."):
                    if isinstance(job_list, dict):
                        job_list = job_list.get(key, [])
                    elif isinstance(job_list, list) and key.isdigit():
                        idx = int(key)
                        job_list = job_list[idx] if idx < len(job_list) else []
                    else:
                        job_list = []
                        break

            if not isinstance(job_list, list):
                continue

            for item in job_list:
                if not isinstance(item, dict):
                    continue

                title = self._deep_get(item, title_key, "")
                if not title:
                    continue

                location = self._deep_get(item, location_key, "")
                if isinstance(location, list):
                    location = ", ".join(str(l) for l in location)

                url = self._deep_get(item, url_key, "")
                if url and not url.startswith("http"):
                    url = normalize_url(url, self.base_url)

                jobs.append({
                    "title": str(title).strip(),
                    "company": str(self._deep_get(item, company_key, "")).strip(),
                    "location": str(location).strip(),
                    "url": url,
                    "salary": "",
                    "posted_date": None,
                    "description": str(self._deep_get(item, description_key, "")).strip()[:2000],
                })

        return jobs

    @staticmethod
    def _deep_get(d: dict, path: str, default: Any = "") -> Any:
        """Get a value from a nested dict using dot-separated path."""
        keys = path.split(".")
        current = d
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current

    async def _extract_jobs_css(self, page: Page) -> list[dict]:
        """Extract jobs using CSS selectors (fallback when interception isn't configured)."""
        jobs = []
        card_selector = self.selectors.get(
            "job_card",
            ".job-card, .job-listing, .job-item, .posting, [data-job], .job-result, .result-card",
        )

        cards = await page.query_selector_all(card_selector)
        if not cards:
            logger.warning("No job cards found with selector: %s", card_selector)
            return jobs

        for card in cards:
            try:
                # Title
                title_sel = self.selectors.get("title", "h2 a, h3 a, .job-title a, .title a")
                title_el = await card.query_selector(title_sel)
                title = (await title_el.inner_text()).strip() if title_el else ""
                if not title:
                    continue

                # URL
                link_sel = self.selectors.get("link", "a[href]")
                link_el = await card.query_selector(link_sel)
                href = await link_el.get_attribute("href") if link_el else ""
                url = normalize_url(href, self.base_url) if href else ""

                # Location
                loc_sel = self.selectors.get("location", ".location, .job-location")
                loc_el = await card.query_selector(loc_sel)
                location = (await loc_el.inner_text()).strip() if loc_el else ""

                # Company
                comp_sel = self.selectors.get("company", ".company, .company-name")
                comp_el = await card.query_selector(comp_sel)
                company = (await comp_el.inner_text()).strip() if comp_el else ""

                # Description
                desc_sel = self.selectors.get("description", ".description, .summary")
                desc_el = await card.query_selector(desc_sel)
                description = (await desc_el.inner_text()).strip() if desc_el else ""

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "salary": "",
                    "posted_date": None,
                    "description": description[:2000],
                })
            except Exception:
                logger.debug("Failed to extract job card", exc_info=True)
                continue

        return jobs

    async def _go_to_next_page(self, page: Page) -> bool:
        """Handle pagination via click or scroll."""
        pagination_type = self.config.get("pagination_type", "click")
        next_selector = self.selectors.get(
            "next_page",
            ".next, .pagination .next, a[rel='next'], button:has-text('Next')",
        )

        try:
            if pagination_type == "infinite_scroll":
                old_height = await page.evaluate("document.body.scrollHeight")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_delay(2.0, 4.0)
                new_height = await page.evaluate("document.body.scrollHeight")
                return new_height > old_height

            # Click-based pagination
            next_btn = await page.query_selector(next_selector)
            if next_btn:
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled is None:
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    return True

            return False
        except Exception:
            logger.debug("Pagination failed", exc_info=True)
            return False
