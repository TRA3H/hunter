import sys
sys.path.insert(0, "/home/traeh/Dev/projects/hunter")

from unittest.mock import AsyncMock, MagicMock

import pytest

from scrapers.greenhouse_scraper import GreenhouseScraper


BASE_URL = "https://boards.greenhouse.io/testcompany"


@pytest.fixture
def scraper():
    return GreenhouseScraper(base_url=BASE_URL)


def _make_section_element(title: str, href: str, location: str | None = None):
    """Create a mock section element with a link child and optional location child."""
    link_el = AsyncMock()
    link_el.inner_text = AsyncMock(return_value=title)
    link_el.get_attribute = AsyncMock(return_value=href)

    location_el = None
    if location is not None:
        location_el = AsyncMock()
        location_el.inner_text = AsyncMock(return_value=location)

    section = AsyncMock()
    async def query_selector(selector):
        if selector == "a":
            return link_el
        if selector == ".location, span:last-child":
            return location_el
        return None
    section.query_selector = AsyncMock(side_effect=query_selector)

    return section


def _make_link_element(title: str, href: str):
    """Create a mock <a> element for the fallback link path."""
    link = AsyncMock()
    link.inner_text = AsyncMock(return_value=title)
    link.get_attribute = AsyncMock(return_value=href)
    return link


def _make_page(sections_primary=None, sections_secondary=None, links_fallback=None,
               company_el=None):
    """Build a mock Playwright Page with configurable query_selector_all responses."""
    page = AsyncMock()

    call_map = {
        "section.level-0, .opening": sections_primary or [],
        "[data-mapped='true'] .opening, .job-post": sections_secondary or [],
        'a[href*="/jobs/"]': links_fallback or [],
    }

    page.query_selector_all = AsyncMock(side_effect=lambda sel: call_map.get(sel, []))
    page.query_selector = AsyncMock(return_value=company_el)

    return page


# --- Test 1: Import and instantiation ---

class TestInstantiation:
    def test_inherits_base_scraper(self, scraper):
        from scrapers.base_scraper import BaseScraper
        assert isinstance(scraper, BaseScraper)

    def test_base_url_set(self, scraper):
        assert scraper.base_url == BASE_URL

    def test_default_config(self, scraper):
        assert scraper.config == {}

    def test_custom_config(self):
        s = GreenhouseScraper(base_url=BASE_URL, config={"max_pages": 10})
        assert s.max_pages == 10


# --- Test 2: extract_jobs with standard sections ---

class TestExtractJobsStandardSections:
    @pytest.mark.asyncio
    async def test_single_job(self, scraper):
        section = _make_section_element("Software Engineer", "/jobs/123", "San Francisco, CA")
        page = _make_page(sections_primary=[section])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Software Engineer"
        assert jobs[0]["location"] == "San Francisco, CA"
        assert jobs[0]["url"] == "https://boards.greenhouse.io/jobs/123"

    @pytest.mark.asyncio
    async def test_multiple_jobs(self, scraper):
        sections = [
            _make_section_element("Engineer", "/jobs/1", "NYC"),
            _make_section_element("Designer", "/jobs/2", "Remote"),
        ]
        page = _make_page(sections_primary=sections)

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Engineer"
        assert jobs[1]["title"] == "Designer"

    @pytest.mark.asyncio
    async def test_no_location_element(self, scraper):
        section = _make_section_element("PM", "/jobs/5", None)
        page = _make_page(sections_primary=[section])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 1
        assert jobs[0]["location"] == ""

    @pytest.mark.asyncio
    async def test_section_without_link_is_skipped(self, scraper):
        section = AsyncMock()
        section.query_selector = AsyncMock(return_value=None)
        page = _make_page(sections_primary=[section])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_uses_secondary_selector_when_primary_empty(self, scraper):
        section = _make_section_element("Data Scientist", "/jobs/99", "Berlin")
        page = _make_page(sections_primary=[], sections_secondary=[section])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Data Scientist"


# --- Test 3: extract_jobs with fallback to job links ---

class TestExtractJobsFallbackLinks:
    @pytest.mark.asyncio
    async def test_fallback_to_links(self, scraper):
        links = [
            _make_link_element("Backend Dev", "https://boards.greenhouse.io/testcompany/jobs/42"),
            _make_link_element("Frontend Dev", "/jobs/43"),
        ]
        page = _make_page(links_fallback=links)

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Backend Dev"
        assert jobs[0]["url"] == "https://boards.greenhouse.io/testcompany/jobs/42"
        assert jobs[1]["title"] == "Frontend Dev"
        assert jobs[1]["url"] == "https://boards.greenhouse.io/jobs/43"

    @pytest.mark.asyncio
    async def test_fallback_jobs_have_empty_fields(self, scraper):
        links = [_make_link_element("Analyst", "/jobs/10")]
        page = _make_page(links_fallback=links)

        jobs = await scraper.extract_jobs(page)
        assert jobs[0]["company"] == ""
        assert jobs[0]["location"] == ""
        assert jobs[0]["salary"] == ""
        assert jobs[0]["description"] == ""
        assert jobs[0]["posted_date"] is None

    @pytest.mark.asyncio
    async def test_fallback_link_with_empty_title_skipped(self, scraper):
        link = _make_link_element("", "/jobs/10")
        page = _make_page(links_fallback=[link])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_fallback_link_with_no_href_skipped(self, scraper):
        link = _make_link_element("Some Job", None)
        page = _make_page(links_fallback=[link])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_fallback_link_exception_continues(self, scraper):
        bad_link = AsyncMock()
        bad_link.inner_text = AsyncMock(side_effect=Exception("boom"))
        good_link = _make_link_element("Good Job", "/jobs/7")
        page = _make_page(links_fallback=[bad_link, good_link])

        jobs = await scraper.extract_jobs(page)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Good Job"


# --- Test 4: extract_jobs with no jobs found ---

class TestExtractJobsEmpty:
    @pytest.mark.asyncio
    async def test_no_jobs_found(self, scraper):
        page = _make_page()

        jobs = await scraper.extract_jobs(page)
        assert jobs == []


# --- Test 5: Company name extraction ---

class TestCompanyNameExtraction:
    @pytest.mark.asyncio
    async def test_company_name_applied_to_all_jobs(self, scraper):
        sections = [
            _make_section_element("Job A", "/jobs/1", "NYC"),
            _make_section_element("Job B", "/jobs/2", "LA"),
        ]
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="Acme Corp")
        page = _make_page(sections_primary=sections, company_el=company_el)

        jobs = await scraper.extract_jobs(page)
        assert all(j["company"] == "Acme Corp" for j in jobs)

    @pytest.mark.asyncio
    async def test_no_company_element(self, scraper):
        section = _make_section_element("Job C", "/jobs/3", "Remote")
        page = _make_page(sections_primary=[section], company_el=None)

        jobs = await scraper.extract_jobs(page)
        assert jobs[0]["company"] == ""

    @pytest.mark.asyncio
    async def test_empty_company_name_not_applied(self, scraper):
        section = _make_section_element("Job D", "/jobs/4", "Remote")
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="   ")
        page = _make_page(sections_primary=[section], company_el=company_el)

        jobs = await scraper.extract_jobs(page)
        assert jobs[0]["company"] == ""

    @pytest.mark.asyncio
    async def test_company_not_applied_for_fallback_links(self, scraper):
        """Fallback link path returns early before company extraction."""
        link = _make_link_element("Dev", "/jobs/55")
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="Should Not Apply")
        page = _make_page(links_fallback=[link], company_el=company_el)

        jobs = await scraper.extract_jobs(page)
        assert jobs[0]["company"] == ""


# --- Test 6: go_to_next_page always returns False ---

class TestGoToNextPage:
    @pytest.mark.asyncio
    async def test_returns_false(self, scraper):
        page = AsyncMock()
        result = await scraper.go_to_next_page(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_multiple_calls(self, scraper):
        page = AsyncMock()
        for _ in range(3):
            assert await scraper.go_to_next_page(page) is False
