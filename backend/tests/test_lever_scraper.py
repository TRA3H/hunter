import sys
sys.path.insert(0, "/home/traeh/Dev/projects/hunter")

import pytest
from unittest.mock import AsyncMock, MagicMock

from scrapers.lever_scraper import LeverScraper


@pytest.fixture
def scraper():
    return LeverScraper(base_url="https://jobs.lever.co/testcompany")


def _make_element(inner_text="", get_attribute_val=None, sub_elements=None, evaluate_val=""):
    """Helper to create a mock Playwright element."""
    el = AsyncMock()
    el.inner_text = AsyncMock(return_value=inner_text)
    el.get_attribute = AsyncMock(return_value=get_attribute_val)
    el.evaluate = AsyncMock(return_value=evaluate_val)

    # sub_elements maps CSS selectors to mock elements (or None)
    sub_elements = sub_elements or {}

    async def mock_query_selector(selector):
        return sub_elements.get(selector)

    el.query_selector = AsyncMock(side_effect=mock_query_selector)
    return el


class TestImportAndInstantiation:
    def test_import(self):
        from scrapers.lever_scraper import LeverScraper as LS
        assert LS is not None

    def test_instantiation(self, scraper):
        assert scraper.base_url == "https://jobs.lever.co/testcompany"
        assert isinstance(scraper, LeverScraper)

    def test_inherits_base_scraper(self, scraper):
        from scrapers.base_scraper import BaseScraper
        assert isinstance(scraper, BaseScraper)


class TestExtractJobsStandardPostings:
    @pytest.mark.asyncio
    async def test_standard_postings(self, scraper):
        """Standard .posting elements with title, link, location, team, commitment."""
        title_el = _make_element(inner_text="Senior Engineer")
        link_el = _make_element(get_attribute_val="https://jobs.lever.co/testcompany/abc123")
        location_el = _make_element(inner_text="San Francisco, CA")
        team_el = _make_element(inner_text="Engineering")
        commitment_el = _make_element(inner_text="Full-time")

        posting = AsyncMock()

        async def posting_qs(selector):
            mapping = {
                "h5, .posting-name, [data-qa='posting-name']": title_el,
                "a.posting-title, a[href]": link_el,
                ".posting-categories .location, .sort-by-location, span.workplaceTypes": location_el,
                ".posting-categories .department, .sort-by-team": team_el,
                ".posting-categories .commitment": commitment_el,
            }
            return mapping.get(selector)

        posting.query_selector = AsyncMock(side_effect=posting_qs)

        company_el = _make_element(inner_text="Test Company")

        page = AsyncMock()
        call_count = 0

        async def page_qsa(selector):
            nonlocal call_count
            if selector == ".posting":
                return [posting]
            return []

        page.query_selector_all = AsyncMock(side_effect=page_qsa)
        page.query_selector = AsyncMock(return_value=company_el)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Senior Engineer"
        assert jobs[0]["url"] == "https://jobs.lever.co/testcompany/abc123"
        assert jobs[0]["location"] == "San Francisco, CA"
        assert jobs[0]["description"] == "Engineering | Full-time"
        assert jobs[0]["company"] == "Test Company"

    @pytest.mark.asyncio
    async def test_posting_without_location_team_commitment(self, scraper):
        """Posting with only title and link, no location/team/commitment."""
        title_el = _make_element(inner_text="Designer")
        link_el = _make_element(get_attribute_val="https://jobs.lever.co/testcompany/xyz")

        posting = AsyncMock()

        async def posting_qs(selector):
            mapping = {
                "h5, .posting-name, [data-qa='posting-name']": title_el,
                "a.posting-title, a[href]": link_el,
                ".posting-categories .location, .sort-by-location, span.workplaceTypes": None,
                ".posting-categories .department, .sort-by-team": None,
                ".posting-categories .commitment": None,
            }
            return mapping.get(selector)

        posting.query_selector = AsyncMock(side_effect=posting_qs)

        page = AsyncMock()
        page.query_selector_all = AsyncMock(side_effect=lambda sel: [posting] if sel == ".posting" else [])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Designer"
        assert jobs[0]["location"] == ""
        assert jobs[0]["description"] == ""
        assert jobs[0]["company"] == ""

    @pytest.mark.asyncio
    async def test_posting_title_fallback_to_anchor(self, scraper):
        """When h5/.posting-name not found, falls back to <a> for title."""
        anchor_el = _make_element(inner_text="Product Manager", get_attribute_val="https://jobs.lever.co/testcompany/pm1")

        posting = AsyncMock()

        async def posting_qs(selector):
            if selector == "h5, .posting-name, [data-qa='posting-name']":
                return None
            if selector == "a":
                return anchor_el
            if selector == "a.posting-title, a[href]":
                return anchor_el
            return None

        posting.query_selector = AsyncMock(side_effect=posting_qs)

        page = AsyncMock()
        page.query_selector_all = AsyncMock(side_effect=lambda sel: [posting] if sel == ".posting" else [])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Product Manager"

    @pytest.mark.asyncio
    async def test_posting_href_fallback_to_evaluate(self, scraper):
        """When link_el.get_attribute returns None, falls back to evaluate."""
        title_el = _make_element(inner_text="Analyst")
        link_el = _make_element(get_attribute_val=None)

        posting = AsyncMock()

        async def posting_qs(selector):
            mapping = {
                "h5, .posting-name, [data-qa='posting-name']": title_el,
                "a.posting-title, a[href]": link_el,
                ".posting-categories .location, .sort-by-location, span.workplaceTypes": None,
                ".posting-categories .department, .sort-by-team": None,
                ".posting-categories .commitment": None,
            }
            return mapping.get(selector)

        posting.query_selector = AsyncMock(side_effect=posting_qs)
        posting.evaluate = AsyncMock(return_value="https://jobs.lever.co/testcompany/analyst1")

        page = AsyncMock()
        page.query_selector_all = AsyncMock(side_effect=lambda sel: [posting] if sel == ".posting" else [])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["url"] == "https://jobs.lever.co/testcompany/analyst1"


class TestExtractJobsFallbackToLinks:
    @pytest.mark.asyncio
    async def test_fallback_to_links(self, scraper):
        """When .posting and data-qa selectors return [], falls back to links."""
        link1 = _make_element(inner_text="Software Engineer", get_attribute_val="https://jobs.lever.co/testcompany/jobs/se1")
        link2 = _make_element(inner_text="Data Scientist", get_attribute_val="https://jobs.lever.co/testcompany/apply/ds1")

        page = AsyncMock()

        async def page_qsa(selector):
            if selector == ".posting":
                return []
            if selector == '[data-qa="posting-name"]':
                return []
            if selector == 'a[href*="/jobs/"], a[href*="/apply"]':
                return [link1, link2]
            return []

        page.query_selector_all = AsyncMock(side_effect=page_qsa)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 2
        assert jobs[0]["title"] == "Software Engineer"
        assert jobs[1]["title"] == "Data Scientist"
        assert jobs[0]["company"] == ""
        assert jobs[0]["location"] == ""

    @pytest.mark.asyncio
    async def test_fallback_links_filters_short_titles(self, scraper):
        """Links with title length <= 3 are filtered out."""
        link_short = _make_element(inner_text="PM", get_attribute_val="https://jobs.lever.co/testcompany/jobs/x")
        link_good = _make_element(inner_text="Product Manager", get_attribute_val="https://jobs.lever.co/testcompany/jobs/pm1")

        page = AsyncMock()

        async def page_qsa(selector):
            if selector in (".posting", '[data-qa="posting-name"]'):
                return []
            if selector == 'a[href*="/jobs/"], a[href*="/apply"]':
                return [link_short, link_good]
            return []

        page.query_selector_all = AsyncMock(side_effect=page_qsa)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Product Manager"

    @pytest.mark.asyncio
    async def test_fallback_links_exception_handling(self, scraper):
        """Links that raise exceptions are skipped."""
        bad_link = AsyncMock()
        bad_link.inner_text = AsyncMock(side_effect=Exception("element detached"))

        good_link = _make_element(inner_text="Good Job Title", get_attribute_val="https://jobs.lever.co/testcompany/jobs/g1")

        page = AsyncMock()

        async def page_qsa(selector):
            if selector in (".posting", '[data-qa="posting-name"]'):
                return []
            if selector == 'a[href*="/jobs/"], a[href*="/apply"]':
                return [bad_link, good_link]
            return []

        page.query_selector_all = AsyncMock(side_effect=page_qsa)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Good Job Title"


class TestExtractJobsNoPostings:
    @pytest.mark.asyncio
    async def test_no_postings_found(self, scraper):
        """All selectors return empty lists -> empty result."""
        page = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])

        jobs = await scraper.extract_jobs(page)

        assert jobs == []


class TestCompanyNameExtraction:
    @pytest.mark.asyncio
    async def test_company_name_applied_to_all_jobs(self, scraper):
        """Company name from header is applied to every job."""
        title_el1 = _make_element(inner_text="Role A")
        link_el1 = _make_element(get_attribute_val="https://jobs.lever.co/testcompany/a")
        title_el2 = _make_element(inner_text="Role B")
        link_el2 = _make_element(get_attribute_val="https://jobs.lever.co/testcompany/b")

        def make_posting(title_el, link_el):
            posting = AsyncMock()

            async def qs(selector):
                if selector == "h5, .posting-name, [data-qa='posting-name']":
                    return title_el
                if selector == "a.posting-title, a[href]":
                    return link_el
                return None

            posting.query_selector = AsyncMock(side_effect=qs)
            return posting

        p1 = make_posting(title_el1, link_el1)
        p2 = make_posting(title_el2, link_el2)

        company_el = _make_element(inner_text="Acme Corp")

        page = AsyncMock()
        page.query_selector_all = AsyncMock(side_effect=lambda sel: [p1, p2] if sel == ".posting" else [])
        page.query_selector = AsyncMock(return_value=company_el)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 2
        assert all(j["company"] == "Acme Corp" for j in jobs)

    @pytest.mark.asyncio
    async def test_no_company_element(self, scraper):
        """When company header element is not found, company stays empty."""
        title_el = _make_element(inner_text="Some Role")
        link_el = _make_element(get_attribute_val="https://jobs.lever.co/testcompany/sr")

        posting = AsyncMock()

        async def qs(selector):
            if selector == "h5, .posting-name, [data-qa='posting-name']":
                return title_el
            if selector == "a.posting-title, a[href]":
                return link_el
            return None

        posting.query_selector = AsyncMock(side_effect=qs)

        page = AsyncMock()
        page.query_selector_all = AsyncMock(side_effect=lambda sel: [posting] if sel == ".posting" else [])
        page.query_selector = AsyncMock(return_value=None)

        jobs = await scraper.extract_jobs(page)

        assert len(jobs) == 1
        assert jobs[0]["company"] == ""


class TestGoToNextPage:
    @pytest.mark.asyncio
    async def test_always_returns_false(self, scraper):
        page = AsyncMock()
        result = await scraper.go_to_next_page(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_multiple_calls(self, scraper):
        page = AsyncMock()
        for _ in range(3):
            assert await scraper.go_to_next_page(page) is False
