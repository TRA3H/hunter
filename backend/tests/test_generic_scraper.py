import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.generic_scraper import DEFAULT_SELECTORS, GenericScraper


# ---------------------------------------------------------------------------
# Helpers to build mock Playwright elements
# ---------------------------------------------------------------------------

def _make_element(
    inner_text="",
    get_attribute_map=None,
    query_selector_map=None,
):
    """Return an AsyncMock that behaves like a Playwright ElementHandle."""
    el = AsyncMock()
    el.inner_text.return_value = inner_text
    get_attribute_map = get_attribute_map or {}
    el.get_attribute = AsyncMock(side_effect=lambda attr: get_attribute_map.get(attr))

    # query_selector returns sub-elements keyed by selector string
    query_selector_map = query_selector_map or {}

    async def _qs(selector):
        return query_selector_map.get(selector)

    el.query_selector = AsyncMock(side_effect=_qs)
    return el


def _make_job_card(
    title="Software Engineer",
    url="/jobs/123",
    company="Acme Corp",
    location="Remote",
    salary="$100k",
    posted_date="2025-01-15",
    description="Great job",
    selectors=None,
):
    """Build a mock card element that has child sub-elements for each field."""
    selectors = selectors or DEFAULT_SELECTORS

    title_el = _make_element(
        inner_text=title,
        get_attribute_map={"href": url},
    )
    link_el = _make_element(get_attribute_map={"href": url})
    company_el = _make_element(inner_text=company)
    location_el = _make_element(inner_text=location)
    salary_el = _make_element(inner_text=salary)
    date_el = _make_element(
        inner_text=posted_date,
        get_attribute_map={"datetime": posted_date},
    )
    desc_el = _make_element(inner_text=description)

    sub_map = {
        selectors["title"]: title_el,
        selectors["link"]: link_el,
        selectors["company"]: company_el,
        selectors["location"]: location_el,
        selectors["salary"]: salary_el,
        selectors["posted_date"]: date_el,
        selectors["description"]: desc_el,
    }

    card = _make_element(
        inner_text=f"{title}\n{company}\n{location}",
        get_attribute_map={"href": url},
        query_selector_map=sub_map,
    )
    return card


def _make_page(query_selector_all_return=None, query_selector_return=None):
    """Return an AsyncMock that behaves like a Playwright Page."""
    page = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=query_selector_all_return or [])
    page.query_selector = AsyncMock(return_value=query_selector_return)
    page.wait_for_load_state = AsyncMock()
    page.evaluate = AsyncMock()
    return page


# ===========================================================================
# 1. Import and instantiation
# ===========================================================================

class TestInstantiation:
    def test_default_config(self):
        scraper = GenericScraper("https://example.com/jobs")
        assert scraper.base_url == "https://example.com/jobs"
        assert scraper.selectors == DEFAULT_SELECTORS
        assert scraper.pagination_type == "click"
        assert scraper.max_pages == 5

    def test_custom_selectors_merged(self):
        custom = {"selectors": {"job_card": ".custom-card", "title": ".custom-title"}}
        scraper = GenericScraper("https://example.com", custom)
        # Custom selectors should override defaults
        assert scraper.selectors["job_card"] == ".custom-card"
        assert scraper.selectors["title"] == ".custom-title"
        # Non-overridden selectors remain default
        assert scraper.selectors["company"] == DEFAULT_SELECTORS["company"]
        assert scraper.selectors["location"] == DEFAULT_SELECTORS["location"]

    def test_custom_pagination_type(self):
        scraper = GenericScraper("https://example.com", {"pagination_type": "infinite_scroll"})
        assert scraper.pagination_type == "infinite_scroll"

    def test_none_selectors_in_config(self):
        scraper = GenericScraper("https://example.com", {"selectors": None})
        assert scraper.selectors == DEFAULT_SELECTORS


# ===========================================================================
# 2. extract_jobs with mocked cards
# ===========================================================================

class TestExtractJobs:
    @pytest.mark.asyncio
    async def test_extract_single_job(self):
        card = _make_job_card()
        page = _make_page(query_selector_all_return=[card])
        scraper = GenericScraper("https://example.com")

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "Software Engineer"
        assert job["url"] == "https://example.com/jobs/123"
        assert job["company"] == "Acme Corp"
        assert job["location"] == "Remote"
        assert job["salary"] == "$100k"
        assert job["posted_date"] == "2025-01-15"
        assert job["description"] == "Great job"

    @pytest.mark.asyncio
    async def test_extract_multiple_jobs(self):
        cards = [
            _make_job_card(title="Job A", url="/a", company="Co A"),
            _make_job_card(title="Job B", url="/b", company="Co B"),
        ]
        page = _make_page(query_selector_all_return=cards)
        scraper = GenericScraper("https://example.com")

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Job A"
        assert jobs[1]["title"] == "Job B"

    @pytest.mark.asyncio
    async def test_extract_jobs_skips_card_without_title(self):
        """Cards missing both title and url should be skipped."""
        card = _make_element(
            inner_text="",
            get_attribute_map={},
            query_selector_map={},
        )
        # query_selector returns None for all selectors (no sub-elements)
        page = _make_page(query_selector_all_return=[card])
        scraper = GenericScraper("https://example.com")

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_extract_jobs_uses_custom_selectors(self):
        custom_selectors = {
            "job_card": ".my-card",
            "title": ".my-title",
            "link": ".my-link",
            "company": ".my-company",
            "location": ".my-loc",
            "salary": ".my-salary",
            "posted_date": ".my-date",
            "description": ".my-desc",
        }
        scraper = GenericScraper("https://example.com", {"selectors": custom_selectors})
        card = _make_job_card(selectors=scraper.selectors)
        page = _make_page(query_selector_all_return=[card])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 1
        # Verify the custom job_card selector was used
        page.query_selector_all.assert_called_with(".my-card")


# ===========================================================================
# 3. extract_jobs with no cards and no fallback links
# ===========================================================================

class TestExtractJobsEmpty:
    @pytest.mark.asyncio
    async def test_no_cards_no_fallback(self):
        """When primary selector AND fallback both return empty, result is empty."""
        page = AsyncMock()
        # Both calls to query_selector_all return []
        page.query_selector_all = AsyncMock(return_value=[])
        scraper = GenericScraper("https://example.com")

        jobs = await scraper.extract_jobs(page)
        assert jobs == []
        # Should have been called twice: once for job_card selector, once for fallback
        assert page.query_selector_all.call_count == 2


# ===========================================================================
# 4. go_to_next_page -- click pagination
# ===========================================================================

class TestPaginateClick:
    @pytest.mark.asyncio
    async def test_click_next_button_exists(self):
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(side_effect=lambda attr: {
            "disabled": None,
            "class": "next",
        }.get(attr))
        next_btn.click = AsyncMock()

        page = _make_page(query_selector_return=next_btn)
        scraper = GenericScraper("https://example.com")

        result = await scraper.go_to_next_page(page)
        assert result is True
        next_btn.click.assert_awaited_once()
        page.wait_for_load_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_next_button_disabled_attr(self):
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(side_effect=lambda attr: {
            "disabled": "",  # disabled attribute present (empty string, not None)
            "class": "next",
        }.get(attr))

        page = _make_page(query_selector_return=next_btn)
        scraper = GenericScraper("https://example.com")

        result = await scraper.go_to_next_page(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_click_next_button_disabled_class(self):
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(side_effect=lambda attr: {
            "disabled": None,
            "class": "next disabled",
        }.get(attr))

        page = _make_page(query_selector_return=next_btn)
        scraper = GenericScraper("https://example.com")

        result = await scraper.go_to_next_page(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_click_no_next_button(self):
        page = _make_page(query_selector_return=None)
        scraper = GenericScraper("https://example.com")

        result = await scraper.go_to_next_page(page)
        assert result is False


# ===========================================================================
# 5. go_to_next_page -- infinite_scroll pagination
# ===========================================================================

class TestPaginateScroll:
    @pytest.mark.asyncio
    @patch("scrapers.generic_scraper.random_delay", new_callable=AsyncMock)
    async def test_scroll_height_changes(self, mock_delay):
        page = _make_page()
        # First evaluate: prev_height, second: scroll (ignored), third: new_height
        page.evaluate = AsyncMock(side_effect=[1000, None, 2000])
        scraper = GenericScraper("https://example.com", {"pagination_type": "infinite_scroll"})

        result = await scraper.go_to_next_page(page)
        assert result is True

    @pytest.mark.asyncio
    @patch("scrapers.generic_scraper.random_delay", new_callable=AsyncMock)
    async def test_scroll_height_unchanged(self, mock_delay):
        page = _make_page()
        page.evaluate = AsyncMock(side_effect=[1000, None, 1000])
        scraper = GenericScraper("https://example.com", {"pagination_type": "infinite_scroll"})

        result = await scraper.go_to_next_page(page)
        assert result is False


# ===========================================================================
# 6. go_to_next_page -- url_param falls back to click
# ===========================================================================

class TestPaginateUrl:
    @pytest.mark.asyncio
    async def test_url_param_falls_back_to_click(self):
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(side_effect=lambda attr: {
            "disabled": None,
            "class": "next",
        }.get(attr))
        next_btn.click = AsyncMock()

        page = _make_page(query_selector_return=next_btn)
        scraper = GenericScraper("https://example.com", {"pagination_type": "url_param"})

        result = await scraper.go_to_next_page(page)
        assert result is True
        # URL pagination navigates via page.goto instead of clicking
        page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_pagination_type_returns_false(self):
        page = _make_page()
        scraper = GenericScraper("https://example.com", {"pagination_type": "unknown"})

        result = await scraper.go_to_next_page(page)
        assert result is False
