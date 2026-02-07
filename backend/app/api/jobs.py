import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, desc, asc, func as sa_func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.board import JobBoard
from app.models.job import Job
from app.models.application import Application
from app.schemas.job import JobFilters, JobListResponse, JobResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _build_job_query(filters: JobFilters) -> Select:
    query = select(Job)

    if filters.search:
        query = query.where(
            Job.description_tsv.op("@@")(sa_func.plainto_tsquery("english", filters.search))
        )

    if filters.board_id:
        query = query.where(Job.board_id == filters.board_id)

    if filters.min_score is not None:
        query = query.where(Job.match_score >= filters.min_score)

    if filters.max_score is not None:
        query = query.where(Job.match_score <= filters.max_score)

    if filters.location:
        query = query.where(Job.location.ilike(f"%{filters.location}%"))

    if filters.is_new is not None:
        query = query.where(Job.is_new == filters.is_new)

    if filters.is_hidden is not None:
        query = query.where(Job.is_hidden == filters.is_hidden)
    else:
        query = query.where(Job.is_hidden == False)

    sort_col = getattr(Job, filters.sort_by, Job.created_at)
    if filters.sort_order == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    return query


@router.get("", response_model=JobListResponse)
async def list_jobs(
    search: str | None = None,
    board_id: uuid.UUID | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    location: str | None = None,
    is_new: bool | None = None,
    is_hidden: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    filters = JobFilters(
        search=search,
        board_id=board_id,
        min_score=min_score,
        max_score=max_score,
        location=location,
        is_new=is_new,
        is_hidden=is_hidden,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    query = _build_job_query(filters)

    # Count total
    count_query = select(sa_func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (filters.page - 1) * filters.page_size
    query = query.offset(offset).limit(filters.page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Enrich with board names and application status
    job_responses = []
    for job in jobs:
        jr = JobResponse.model_validate(job)
        # Get board name
        board_result = await db.execute(select(JobBoard.name).where(JobBoard.id == job.board_id))
        jr.board_name = board_result.scalar_one_or_none()
        # Get application status
        app_result = await db.execute(
            select(Application.status)
            .where(Application.job_id == job.id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        jr.application_status = app_result.scalar_one_or_none()
        job_responses.append(jr)

    return JobListResponse(jobs=job_responses, total=total, page=filters.page, page_size=filters.page_size)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    jr = JobResponse.model_validate(job)
    board_result = await db.execute(select(JobBoard.name).where(JobBoard.id == job.board_id))
    jr.board_name = board_result.scalar_one_or_none()
    return jr


@router.patch("/{job_id}/hide", response_model=JobResponse)
async def toggle_hide_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_hidden = not job.is_hidden
    await db.flush()
    await db.refresh(job)
    return JobResponse.model_validate(job)


@router.patch("/{job_id}/read", response_model=JobResponse)
async def mark_job_read(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_new = False
    await db.flush()
    await db.refresh(job)
    return JobResponse.model_validate(job)
