import asyncio
import logging
import random
from urllib.parse import urlparse

import httpx
from robotexclusionrulesparser import RobotExclusionRulesParser

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def random_delay(min_seconds: float = 2.0, max_seconds: float = 8.0):
    """Wait a random amount of time to avoid detection."""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Waiting %.1f seconds", delay)
    await asyncio.sleep(delay)


async def check_robots_txt(url: str) -> bool:
    """Check if scraping is allowed by robots.txt.
    Returns True if allowed, False if disallowed.
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        async with httpx.AsyncClient() as client:
            response = await client.get(robots_url, timeout=10)

        if response.status_code != 200:
            return True  # No robots.txt = allowed

        parser = RobotExclusionRulesParser()
        parser.parse(response.text)

        user_agent = "HunterBot"
        return parser.is_allowed(user_agent, url)

    except Exception:
        logger.warning("Could not check robots.txt for %s, proceeding", url)
        return True


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    parsed = urlparse(url)
    return parsed.netloc


def normalize_url(url: str, base_url: str) -> str:
    """Normalize a potentially relative URL to absolute."""
    if url.startswith("http"):
        return url
    parsed_base = urlparse(base_url)
    if url.startswith("//"):
        return f"{parsed_base.scheme}:{url}"
    if url.startswith("/"):
        return f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
    return f"{base_url.rstrip('/')}/{url.lstrip('/')}"
