import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.workday_scraper import WorkdayScraper


@pytest.fixture
def scraper():
    return WorkdayScraper(base_url="https://company.wd5.myworkdayjobs.com/en-US/jobs")


def _make_card(tag="a", title="Software Engineer", href="/job/12345", parent_texts=None):
    """Helper to build a mock job card element."""
    card = AsyncMock()

    async def evaluate_side_effect(expr):
        if "tagName" in expr:
            return tag
        # parent evaluation
        return {"texts": parent_texts or []}

    card.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    card.inner_text = AsyncMock(return_value=f"  {title}  ")
    card.get_attribute = AsyncMock(return_value=href)
    # For non-anchor tags, provide a nested link
    inner_link = AsyncMock()
    inner_link.get_attribute = AsyncMock(return_value=href)
    card.query_selector = AsyncMock(return_value=inner_link)
    return card


@patch("scrapers.workday_scraper.random_delay", new_callable=AsyncMock)
class TestExtractJobs:

    @pytest.mark.asyncio
    async def test_extract_jobs_with_cards(self, mock_delay, scraper):
        page = AsyncMock()
        card1 = _make_card(tag="a", title="Backend Dev", href="/job/1", parent_texts=["New York, NY"])
        card2 = _make_card(tag="a", title="Frontend Dev", href="/job/2", parent_texts=["Remote"])

        page.query_selector_all = AsyncMock(return_value=[card1, card2])
        # company element
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="  Acme Corp  ")
        page.query_selector = AsyncMock(return_value=company_el)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 2
        assert jobs[0]["title"] == "Backend Dev"
        assert jobs[0]["url"].endswith("/job/1")
        assert jobs[0]["location"] == "New York, NY"
        assert jobs[1]["title"] == "Frontend Dev"
        assert jobs[1]["location"] == "Remote"
        mock_delay.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_extract_jobs_non_anchor_tag(self, mock_delay, scraper):
        page = AsyncMock()
        card = _make_card(tag="div", title="Data Scientist", href="/job/99", parent_texts=["Boston, MA"])

        page.query_selector_all = AsyncMock(return_value=[card])
        page.query_selector = AsyncMock(return_value=None)  # no company element

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Data Scientist"
        # For non-anchor tags, query_selector("a") is called on the card
        card.query_selector.assert_awaited()

    @pytest.mark.asyncio
    async def test_extract_jobs_no_cards(self, mock_delay, scraper):
        page = AsyncMock()
        # Both query_selector_all calls return empty
        page.query_selector_all = AsyncMock(return_value=[])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert jobs == []

    @pytest.mark.asyncio
    async def test_extract_jobs_skips_card_without_href(self, mock_delay, scraper):
        page = AsyncMock()
        card = _make_card(tag="a", title="No Link Job", href=None)
        page.query_selector_all = AsyncMock(return_value=[card])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert jobs == []

    @pytest.mark.asyncio
    async def test_extract_jobs_skips_card_without_title(self, mock_delay, scraper):
        page = AsyncMock()
        card = _make_card(tag="a", title="", href="/job/1")
        page.query_selector_all = AsyncMock(return_value=[card])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert jobs == []

    @pytest.mark.asyncio
    async def test_extract_jobs_fallback_selectors(self, mock_delay, scraper):
        """When first query_selector_all returns empty, falls back to a[href*='/job/']."""
        page = AsyncMock()
        card = _make_card(tag="a", title="Fallback Job", href="/job/77")
        call_count = 0

        async def qsa_side_effect(selector):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # first selector batch returns nothing
            return [card]  # fallback returns a card

        page.query_selector_all = AsyncMock(side_effect=qsa_side_effect)
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Fallback Job"
        assert page.query_selector_all.await_count == 2

    @pytest.mark.asyncio
    async def test_extract_jobs_wait_for_selector_timeout(self, mock_delay, scraper):
        """If wait_for_selector times out, extraction still proceeds."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        page.query_selector_all = AsyncMock(return_value=[])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert jobs == []

    @pytest.mark.asyncio
    async def test_company_name_applied_to_all_jobs(self, mock_delay, scraper):
        page = AsyncMock()
        cards = [
            _make_card(tag="a", title=f"Job {i}", href=f"/job/{i}")
            for i in range(3)
        ]
        page.query_selector_all = AsyncMock(return_value=cards)

        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="  BigCorp Inc  ")
        page.query_selector = AsyncMock(return_value=company_el)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 3
        for job in jobs:
            assert job["company"] == "BigCorp Inc"

    @pytest.mark.asyncio
    async def test_no_company_element(self, mock_delay, scraper):
        page = AsyncMock()
        card = _make_card(tag="a", title="Solo Job", href="/job/1")
        page.query_selector_all = AsyncMock(return_value=[card])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["company"] == ""

    @pytest.mark.asyncio
    async def test_card_exception_skipped(self, mock_delay, scraper):
        """A card that raises an exception is skipped without breaking the rest."""
        page = AsyncMock()
        bad_card = AsyncMock()
        bad_card.evaluate = AsyncMock(side_effect=Exception("boom"))
        good_card = _make_card(tag="a", title="Good Job", href="/job/1")
        page.query_selector_all = AsyncMock(return_value=[bad_card, good_card])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Good Job"


class TestGoToNextPage:

    @pytest.mark.asyncio
    async def test_show_more_button_enabled(self, scraper):
        page = AsyncMock()
        show_more = AsyncMock()
        show_more.get_attribute = AsyncMock(return_value=None)  # not disabled

        page.query_selector = AsyncMock(return_value=show_more)

        result = await scraper.go_to_next_page(page)

        assert result is True
        show_more.click.assert_awaited_once()
        page.wait_for_timeout.assert_awaited_once_with(3000)

    @pytest.mark.asyncio
    async def test_show_more_button_disabled(self, scraper):
        page = AsyncMock()
        show_more = AsyncMock()
        show_more.get_attribute = AsyncMock(return_value="true")  # disabled

        # First query_selector returns show_more (disabled), second returns None (no next btn)
        page.query_selector = AsyncMock(side_effect=[show_more, None])

        result = await scraper.go_to_next_page(page)

        assert result is False
        show_more.click.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_next_arrow_button(self, scraper):
        page = AsyncMock()
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(return_value=None)  # not disabled

        # First query_selector returns None (no show more), second returns next_btn
        page.query_selector = AsyncMock(side_effect=[None, next_btn])

        result = await scraper.go_to_next_page(page)

        assert result is True
        next_btn.click.assert_awaited_once()
        page.wait_for_load_state.assert_awaited_once_with("networkidle", timeout=15000)

    @pytest.mark.asyncio
    async def test_next_arrow_disabled(self, scraper):
        page = AsyncMock()
        next_btn = AsyncMock()
        next_btn.get_attribute = AsyncMock(return_value="true")  # disabled

        # No show more, next button is disabled
        page.query_selector = AsyncMock(side_effect=[None, next_btn])

        result = await scraper.go_to_next_page(page)

        assert result is False
        next_btn.click.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_pagination_buttons(self, scraper):
        page = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)

        result = await scraper.go_to_next_page(page)

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, scraper):
        page = AsyncMock()
        page.query_selector = AsyncMock(side_effect=Exception("network error"))

        result = await scraper.go_to_next_page(page)

        assert result is False


class TestInstantiation:

    def test_import_and_create(self):
        s = WorkdayScraper(base_url="https://example.com/jobs")
        assert s.base_url == "https://example.com/jobs"
        assert s.config == {}
        assert s.max_pages == 5

    def test_with_config(self):
        s = WorkdayScraper(base_url="https://example.com", config={"max_pages": 10})
        assert s.max_pages == 10

    def test_inherits_base_scraper(self):
        from scrapers.base_scraper import BaseScraper
        assert issubclass(WorkdayScraper, BaseScraper)
