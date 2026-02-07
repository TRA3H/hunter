import logging
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.profile import UserProfile

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set[str]:
    """Break text into lowercase tokens for comparison."""
    return set(re.findall(r"[a-zA-Z0-9+#]+", text.lower()))


def compute_keyword_score(job_text: str, keywords: list[str]) -> float:
    """Score 0-100 based on what fraction of keywords appear in the job text."""
    if not keywords:
        return 0.0
    text_lower = job_text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return (matches / len(keywords)) * 100


def compute_title_similarity(job_title: str, desired_title: str) -> float:
    """Score 0-100 based on token overlap between job title and desired title."""
    if not desired_title:
        return 0.0
    job_tokens = _tokenize(job_title)
    desired_tokens = _tokenize(desired_title)
    if not desired_tokens:
        return 0.0
    overlap = job_tokens & desired_tokens
    return (len(overlap) / len(desired_tokens)) * 100


def compute_location_score(job_location: str, desired_locations: str, remote_preference: str) -> float:
    """Score 0-100 based on location matching."""
    if not desired_locations and not remote_preference:
        return 50.0  # Neutral if no preference

    job_loc_lower = job_location.lower()
    score = 0.0

    # Check remote preference
    if remote_preference in ("remote", "any"):
        if "remote" in job_loc_lower:
            return 100.0

    if desired_locations:
        locations = [loc.strip().lower() for loc in desired_locations.split(",")]
        for loc in locations:
            if loc in job_loc_lower:
                return 100.0
        # Partial match: check city/state components
        for loc in locations:
            loc_parts = _tokenize(loc)
            job_parts = _tokenize(job_location)
            if loc_parts & job_parts:
                score = max(score, 60.0)

    return score


def compute_match_score(
    job: Job,
    keywords: list[str],
    desired_title: str,
    desired_locations: str,
    remote_preference: str,
) -> float:
    """Compute overall match score (0-100) for a job against user preferences.

    Weights:
        - Keyword match: 40%
        - Title similarity: 35%
        - Location match: 25%
    """
    job_text = f"{job.title} {job.description}"

    keyword_score = compute_keyword_score(job_text, keywords)
    title_score = compute_title_similarity(job.title, desired_title)
    location_score = compute_location_score(job.location, desired_locations, remote_preference)

    overall = (keyword_score * 0.40) + (title_score * 0.35) + (location_score * 0.25)
    return round(min(overall, 100.0), 1)


async def score_jobs(db: AsyncSession, jobs: list[Job], board_keywords: list[str]) -> list[Job]:
    """Score a list of jobs against the user profile and board keywords."""
    # Load user profile
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()

    desired_title = ""
    desired_locations = ""
    remote_preference = ""

    if profile:
        desired_title = profile.desired_title
        desired_locations = profile.desired_locations
        remote_preference = profile.remote_preference

    for job in jobs:
        job.match_score = compute_match_score(
            job,
            board_keywords,
            desired_title,
            desired_locations,
            remote_preference,
        )

    if jobs:
        await db.flush()

    return jobs


async def fulltext_search(db: AsyncSession, query: str, limit: int = 50) -> list[Job]:
    """Perform PostgreSQL full-text search with ts_rank scoring."""
    result = await db.execute(
        select(Job)
        .where(Job.description_tsv.op("@@")(text("plainto_tsquery('english', :q)")))
        .order_by(text("ts_rank(description_tsv, plainto_tsquery('english', :q)) DESC"))
        .limit(limit),
        {"q": query},
    )
    return list(result.scalars().all())
