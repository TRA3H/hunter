import sys

sys.path.insert(0, "/home/traeh/Dev/projects/hunter")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.utils import (
    USER_AGENTS,
    check_robots_txt,
    extract_domain,
    get_random_user_agent,
    normalize_url,
    random_delay,
)


# --- get_random_user_agent ---


class TestGetRandomUserAgent:
    def test_returns_string_from_user_agents(self):
        result = get_random_user_agent()
        assert isinstance(result, str)
        assert result in USER_AGENTS

    def test_returns_different_values_over_many_calls(self):
        results = {get_random_user_agent() for _ in range(200)}
        assert len(results) > 1


# --- random_delay ---


class TestRandomDelay:
    @pytest.mark.asyncio
    async def test_calls_asyncio_sleep(self):
        with patch("scrapers.utils.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await random_delay(1.0, 3.0)
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]
            assert 1.0 <= delay <= 3.0

    @pytest.mark.asyncio
    async def test_default_range(self):
        with patch("scrapers.utils.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await random_delay()
            delay = mock_sleep.call_args[0][0]
            assert 2.0 <= delay <= 8.0


# --- check_robots_txt ---


def _make_mock_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


class TestCheckRobotsTxt:
    @pytest.mark.asyncio
    async def test_allowed_by_robots(self):
        robots_content = "User-agent: *\nAllow: /\n"
        mock_resp = _make_mock_response(200, robots_content)

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("scrapers.utils.httpx.AsyncClient", return_value=mock_client):
            result = await check_robots_txt("https://example.com/jobs")
        assert result is True

    @pytest.mark.asyncio
    async def test_disallowed_by_robots(self):
        robots_content = "User-agent: HunterBot\nDisallow: /\n"
        mock_resp = _make_mock_response(200, robots_content)

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("scrapers.utils.httpx.AsyncClient", return_value=mock_client):
            result = await check_robots_txt("https://example.com/jobs")
        assert result is False

    @pytest.mark.asyncio
    async def test_404_returns_true(self):
        mock_resp = _make_mock_response(404)

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("scrapers.utils.httpx.AsyncClient", return_value=mock_client):
            result = await check_robots_txt("https://example.com/jobs")
        assert result is True

    @pytest.mark.asyncio
    async def test_network_error_returns_true(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("connection failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("scrapers.utils.httpx.AsyncClient", return_value=mock_client):
            result = await check_robots_txt("https://example.com/jobs")
        assert result is True


# --- extract_domain ---


class TestExtractDomain:
    def test_simple_url(self):
        assert extract_domain("https://example.com/path") == "example.com"

    def test_url_with_port(self):
        assert extract_domain("https://example.com:8080/path") == "example.com:8080"

    def test_url_with_subdomain(self):
        assert extract_domain("https://jobs.example.com/search") == "jobs.example.com"

    def test_http_url(self):
        assert extract_domain("http://example.org") == "example.org"

    def test_url_with_query(self):
        assert extract_domain("https://example.com/path?q=1") == "example.com"


# --- normalize_url ---


class TestNormalizeUrl:
    def test_absolute_url_returned_as_is(self):
        url = "https://other.com/page"
        assert normalize_url(url, "https://example.com") == url

    def test_http_absolute_url_returned_as_is(self):
        url = "http://other.com/page"
        assert normalize_url(url, "https://example.com") == url

    def test_protocol_relative(self):
        result = normalize_url("//cdn.example.com/file.js", "https://example.com/page")
        assert result == "https://cdn.example.com/file.js"

    def test_root_relative(self):
        result = normalize_url("/jobs/123", "https://example.com/careers")
        assert result == "https://example.com/jobs/123"

    def test_relative_path(self):
        result = normalize_url("details/456", "https://example.com/jobs/")
        assert result == "https://example.com/jobs/details/456"

    def test_relative_path_base_no_trailing_slash(self):
        result = normalize_url("details/456", "https://example.com/jobs")
        assert result == "https://example.com/jobs/details/456"
