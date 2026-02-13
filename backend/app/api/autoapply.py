import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.application import Application, ApplicationLog, ApplicationStatus
from app.models.job import Job
from app.models.board import JobBoard
from app.schemas.application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationLogResponse,
    ApplicationResponse,
    ApplicationReview,
    DashboardStats,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _app_to_response(app: Application) -> ApplicationResponse:
    resp = ApplicationResponse.model_validate(app)
    if app.job:
        resp.job_title = app.job.title
        resp.job_company = app.job.company
    return resp


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).options(
        selectinload(Application.logs),
        selectinload(Application.job),
    ).order_by(Application.updated_at.desc())

    if status:
        query = query.where(Application.status == status)

    result = await db.execute(query)
    apps = result.scalars().all()
    return ApplicationListResponse(
        applications=[_app_to_response(a) for a in apps],
        total=len(apps),
    )


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # Active boards
    boards_result = await db.execute(select(sa_func.count()).where(JobBoard.enabled == True))
    active_boards = boards_result.scalar() or 0

    # Job counts
    total_jobs_result = await db.execute(select(sa_func.count()).select_from(Job))
    total_jobs = total_jobs_result.scalar() or 0

    new_jobs_result = await db.execute(select(sa_func.count()).where(Job.is_new == True))
    new_jobs = new_jobs_result.scalar() or 0

    # Application counts
    in_progress_result = await db.execute(
        select(sa_func.count()).where(Application.status == ApplicationStatus.IN_PROGRESS)
    )
    in_progress = in_progress_result.scalar() or 0

    needs_review_result = await db.execute(
        select(sa_func.count()).where(Application.status == ApplicationStatus.NEEDS_REVIEW)
    )
    needs_review = needs_review_result.scalar() or 0

    submitted_result = await db.execute(
        select(sa_func.count()).where(Application.status == ApplicationStatus.SUBMITTED)
    )
    submitted = submitted_result.scalar() or 0

    total_apps_result = await db.execute(select(sa_func.count()).select_from(Application))
    total_apps = total_apps_result.scalar() or 0

    # Jobs per board
    jobs_by_board_result = await db.execute(
        select(JobBoard.name, sa_func.count(Job.id))
        .join(Job, Job.board_id == JobBoard.id)
        .group_by(JobBoard.name)
    )
    jobs_by_board = [{"board": name, "count": count} for name, count in jobs_by_board_result.all()]

    # Applications over time (last 30 days)
    apps_over_time_result = await db.execute(
        select(
            sa_func.date_trunc("day", Application.created_at).label("date"),
            sa_func.count().label("count"),
        )
        .group_by("date")
        .order_by("date")
        .limit(30)
    )
    apps_over_time = [
        {"date": str(row.date.date()) if row.date else "", "count": row.count}
        for row in apps_over_time_result.all()
    ]

    # Recent activity
    logs_result = await db.execute(
        select(ApplicationLog)
        .order_by(ApplicationLog.timestamp.desc())
        .limit(20)
    )
    recent_activity = [
        {"action": log.action, "details": log.details, "timestamp": str(log.timestamp)}
        for log in logs_result.scalars().all()
    ]

    return DashboardStats(
        active_boards=active_boards,
        total_jobs=total_jobs,
        new_jobs=new_jobs,
        in_progress_applications=in_progress,
        needs_review_applications=needs_review,
        submitted_applications=submitted,
        total_applications=total_apps,
        jobs_by_board=jobs_by_board,
        applications_over_time=apps_over_time,
        recent_activity=recent_activity,
    )


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.logs), selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return _app_to_response(app)


@router.post("", response_model=ApplicationResponse, status_code=201)
async def start_application(data: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    # Verify job exists
    job_result = await db.execute(select(Job).where(Job.id == data.job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check for existing active application
    existing = await db.execute(
        select(Application).where(
            Application.job_id == data.job_id,
            Application.status.notin_([ApplicationStatus.FAILED, ApplicationStatus.CANCELLED]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Active application already exists for this job")

    app = Application(job_id=data.job_id, status=ApplicationStatus.PENDING)
    db.add(app)
    await db.flush()

    # Add log entry
    log = ApplicationLog(application_id=app.id, action="created", details=f"Application created for {job.title} at {job.company}")
    db.add(log)
    await db.flush()

    # Commit so the Celery worker can see the row before we dispatch the task
    await db.commit()

    # Launch Celery task after commit
    from app.tasks.apply_tasks import auto_apply_task
    task = auto_apply_task.delay(str(app.id))

    app.celery_task_id = task.id
    await db.commit()

    # Build response manually to avoid MissingGreenlet from lazy attribute access
    return ApplicationResponse(
        id=app.id,
        job_id=app.job_id,
        status=app.status,
        form_fields=None,
        screenshot_path=app.screenshot_path,
        current_page_url=app.current_page_url,
        ai_answers=app.ai_answers,
        error_message=app.error_message,
        celery_task_id=app.celery_task_id,
        created_at=app.created_at,
        updated_at=app.created_at,  # just created, same as created_at
        submitted_at=None,
        logs=[ApplicationLogResponse(
            id=log.id,
            action=log.action,
            details=log.details,
            screenshot_path=log.screenshot_path,
            timestamp=log.timestamp,
        )],
        job_title=job.title,
        job_company=job.company,
    )


@router.post("/{app_id}/review", response_model=ApplicationResponse)
async def submit_review(app_id: uuid.UUID, data: ApplicationReview, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.logs), selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.status != ApplicationStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=400, detail="Application is not in review state")

    app.form_fields = [f.model_dump() for f in data.form_fields]
    app.status = ApplicationStatus.READY_TO_SUBMIT

    log = ApplicationLog(application_id=app.id, action="review_submitted", details="User reviewed and approved form fields")
    db.add(log)
    await db.flush()
    await db.refresh(app, attribute_names=["logs", "job"])

    # Resume the apply task
    from app.tasks.apply_tasks import resume_apply_task
    resume_apply_task.delay(str(app.id))

    return _app_to_response(app)


@router.post("/{app_id}/cancel", response_model=ApplicationResponse)
async def cancel_application(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.logs), selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = ApplicationStatus.CANCELLED
    log = ApplicationLog(application_id=app.id, action="cancelled", details="Application cancelled by user")
    db.add(log)
    await db.flush()
    await db.refresh(app, attribute_names=["logs", "job"])
    return _app_to_response(app)


@router.post("/{app_id}/open-browser", response_model=dict)
async def open_browser(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application).where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.status not in (ApplicationStatus.NEEDS_REVIEW, ApplicationStatus.READY_TO_SUBMIT):
        raise HTTPException(status_code=400, detail="Application must be in needs_review or ready_to_submit status")

    from app.tasks.apply_tasks import open_browser_task
    task = open_browser_task.delay(str(app.id))
    return {"task_id": task.id, "message": "Browser opening with pre-filled form data"}


@router.post("/{app_id}/ai-assist", response_model=dict)
async def request_ai_assist(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    from app.services.ai_assistant import generate_answers
    answers = await generate_answers(app, db)
    app.ai_answers = answers
    await db.flush()

    return {"answers": answers}
