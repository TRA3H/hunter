import hashlib
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import JobBoard
from app.models.job import Job

logger = logging.getLogger(__name__)


def compute_dedup_hash(url: str, title: str, company: str) -> str:
    """Compute a deduplication hash from URL or title+company."""
    # Prefer URL-based dedup; fall back to title+company
    normalized_url = url.strip().lower().rstrip("/")
    if normalized_url:
        return hashlib.sha256(normalized_url.encode()).hexdigest()
    key = f"{title.strip().lower()}|{company.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


def parse_salary(text: str) -> tuple[int | None, int | None]:
    """Extract salary range from text like '$80,000 - $120,000' or '$150K'."""
    if not text:
        return None, None

    # Remove common noise
    text = text.replace(",", "").replace("$", "").strip()

    # Match ranges: "80000 - 120000" or "80k - 120k"
    range_match = re.search(r"(\d+\.?\d*)\s*[kK]?\s*[-–to]+\s*(\d+\.?\d*)\s*[kK]?", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        # Detect K notation
        if low < 1000:
            low *= 1000
        if high < 1000:
            high *= 1000
        return int(low), int(high)

    # Single value: "120000" or "120k"
    single_match = re.search(r"(\d+\.?\d*)\s*[kK]?", text)
    if single_match:
        val = float(single_match.group(1))
        if val < 1000:
            val *= 1000
        return int(val), int(val)

    return None, None


async def store_scraped_jobs(
    db: AsyncSession,
    board_id: str,
    raw_jobs: list[dict],
) -> list[Job]:
    """Store scraped job data, deduplicating against existing records.

    Each raw_job dict should have keys:
        title, company, location, url, posted_date (optional),
        salary (optional string), description
    """
    new_jobs = []
    for raw in raw_jobs:
        title = raw.get("title", "").strip()
        company = raw.get("company", "").strip()
        url = raw.get("url", "").strip()

        if not title or not url:
            logger.warning("Skipping job with missing title or URL: %s", raw)
            continue

        dedup = compute_dedup_hash(url, title, company)

        # Check for existing
        existing = await db.execute(select(Job).where(Job.dedup_hash == dedup))
        if existing.scalar_one_or_none():
            continue

        salary_min, salary_max = parse_salary(raw.get("salary", ""))

        posted_date = None
        if raw.get("posted_date"):
            try:
                if isinstance(raw["posted_date"], str):
                    posted_date = datetime.fromisoformat(raw["posted_date"])
                else:
                    posted_date = raw["posted_date"]
            except (ValueError, TypeError):
                pass

        job = Job(
            board_id=board_id,
            title=title,
            company=company,
            location=raw.get("location", ""),
            url=url,
            posted_date=posted_date,
            salary_min=salary_min,
            salary_max=salary_max,
            description=raw.get("description", ""),
            dedup_hash=dedup,
            is_new=True,
        )
        db.add(job)
        new_jobs.append(job)

    if new_jobs:
        await db.flush()
        for job in new_jobs:
            await db.refresh(job)

    return new_jobs
