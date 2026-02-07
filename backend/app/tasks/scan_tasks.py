import asyncio
import importlib
import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.board import JobBoard
from app.models.job import Job
from app.services.matcher import score_jobs
from app.services.notifier import notify_new_jobs
from app.services.scanner import store_scraped_jobs
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SCRAPERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scrapers")
# In Docker the scrapers are volume-mounted at /opt/scrapers
if not os.path.isdir(SCRAPERS_DIR):
    SCRAPERS_DIR = "/opt/scrapers"

# Ensure the parent of scrapers/ is on sys.path so internal imports
# like "from scrapers.base_scraper import ..." work inside scraper modules
_scrapers_parent = os.path.dirname(os.path.abspath(SCRAPERS_DIR))
if _scrapers_parent not in sys.path:
    sys.path.insert(0, _scrapers_parent)

logger = logging.getLogger(__name__)


def _get_async_session() -> async_sessionmaker:
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _get_scraper_class(scraper_type: str):
    """Dynamically load the appropriate scraper class."""
    scraper_map = {
        "generic": ("scrapers.generic_scraper", "GenericScraper"),
        "workday": ("scrapers.workday_scraper", "WorkdayScraper"),
        "greenhouse": ("scrapers.greenhouse_scraper", "GreenhouseScraper"),
        "lever": ("scrapers.lever_scraper", "LeverScraper"),
    }
    module_path, class_name = scraper_map.get(scraper_type, scraper_map["generic"])
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


async def _run_scan(board_id: str):
    """Execute a scan for a single board."""
    session_factory = _get_async_session()

    async with session_factory() as db:
        result = await db.execute(select(JobBoard).where(JobBoard.id == board_id))
        board = result.scalar_one_or_none()

        if not board:
            logger.error("Board %s not found", board_id)
            return

        if not board.enabled:
            logger.info("Board %s is disabled, skipping scan", board.name)
            return

        logger.info("Starting scan for board: %s (%s)", board.name, board.url)
        board.last_scan_status = "running"
        await db.commit()

        try:
            scraper_config = board.scraper_config or {}
            scraper_type = scraper_config.get("scraper_type", "generic")
            scraper_class = _get_scraper_class(scraper_type)
            scraper = scraper_class(board.url, scraper_config)

            raw_jobs = await scraper.scrape()
            logger.info("Scraped %d raw jobs from %s", len(raw_jobs), board.name)

            # Filter by keywords if configured
            keywords = board.keyword_filters or []
            if keywords:
                filtered = []
                for job in raw_jobs:
                    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
                    if any(kw.lower() in text for kw in keywords):
                        filtered.append(job)
                raw_jobs = filtered
                logger.info("After keyword filtering: %d jobs", len(raw_jobs))

            # Store and deduplicate
            new_jobs = await store_scraped_jobs(db, str(board.id), raw_jobs)
            logger.info("Stored %d new jobs for %s", len(new_jobs), board.name)

            # Score new jobs
            if new_jobs:
                await score_jobs(db, new_jobs, keywords)

            # Update board metadata
            board.last_scanned_at = datetime.now(timezone.utc)
            board.last_scan_status = "success"
            board.last_scan_error = None
            board.jobs_found_last_scan = len(new_jobs)
            await db.commit()

            # Broadcast new jobs via WebSocket
            if new_jobs:
                from app.api.websocket import broadcast_sync

                for job in new_jobs:
                    broadcast_sync("new_job", {
                        "id": str(job.id),
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.url,
                        "match_score": job.match_score,
                        "board_name": board.name,
                    })

                # Send email notification
                notify_new_jobs([
                    {
                        "title": j.title,
                        "company": j.company,
                        "location": j.location,
                        "url": j.url,
                        "match_score": j.match_score,
                    }
                    for j in new_jobs
                ])

        except Exception as e:
            logger.exception("Scan failed for board %s", board.name)
            board.last_scan_status = "error"
            board.last_scan_error = str(e)[:500]
            board.last_scanned_at = datetime.now(timezone.utc)
            await db.commit()

            # Broadcast error
            from app.api.websocket import broadcast_sync
            broadcast_sync("scan_error", {
                "board_id": str(board.id),
                "board_name": board.name,
                "error": str(e)[:200],
            })


@celery.task(name="app.tasks.scan_tasks.scan_board_task", bind=True, max_retries=2)
def scan_board_task(self, board_id: str):
    """Celery task to scan a single board."""
    try:
        asyncio.run(_run_scan(board_id))
    except Exception as exc:
        logger.exception("Scan task failed for board %s", board_id)
        raise self.retry(exc=exc, countdown=60)


@celery.task(name="app.tasks.scan_tasks.check_scan_schedules")
def check_scan_schedules():
    """Periodic task to check which boards need scanning based on their interval."""

    async def _check():
        session_factory = _get_async_session()
        async with session_factory() as db:
            result = await db.execute(select(JobBoard).where(JobBoard.enabled == True))
            boards = result.scalars().all()

            now = datetime.now(timezone.utc)
            for board in boards:
                should_scan = False
                if board.last_scanned_at is None:
                    should_scan = True
                else:
                    elapsed = (now - board.last_scanned_at).total_seconds() / 60
                    if elapsed >= board.scan_interval_minutes:
                        should_scan = True

                if should_scan and board.last_scan_status != "running":
                    logger.info("Scheduling scan for board: %s", board.name)
                    scan_board_task.delay(str(board.id))

    asyncio.run(_check())
