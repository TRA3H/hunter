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
    ApplicationResponse,
    ApplicationUpdate,
    BulkDeleteRequest,
    DashboardStats,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _app_to_response(app: Application) -> ApplicationResponse:
    resp = ApplicationResponse.model_validate(app)
    if app.job:
        resp.job_title = app.job.title
        resp.job_company = app.job.company
        resp.job_url = app.job.url
        resp.match_score = app.job.match_score
    return resp


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    status: str | None = None,
    search: str | None = None,
    job_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).options(
        selectinload(Application.logs),
        selectinload(Application.job),
    ).order_by(Application.updated_at.desc())

    if status:
        query = query.where(Application.status == status)

    if job_id:
        query = query.where(Application.job_id == job_id)

    result = await db.execute(query)
    apps = result.scalars().all()

    responses = [_app_to_response(a) for a in apps]

    if search:
        search_lower = search.lower()
        responses = [
            r for r in responses
            if (r.job_title and search_lower in r.job_title.lower())
            or (r.job_company and search_lower in r.job_company.lower())
            or (r.notes and search_lower in r.notes.lower())
        ]

    return ApplicationListResponse(
        applications=responses,
        total=len(responses),
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

    # Total applications
    total_apps_result = await db.execute(select(sa_func.count()).select_from(Application))
    total_apps = total_apps_result.scalar() or 0

    # Applications by status
    status_counts = {}
    for s in ApplicationStatus:
        count_result = await db.execute(
            select(sa_func.count()).where(Application.status == s.value)
        )
        count = count_result.scalar() or 0
        if count > 0:
            status_counts[s.value] = count

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
        total_applications=total_apps,
        applications_by_status=status_counts,
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
async def create_application(data: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    # Verify job exists if job_id provided
    job = None
    if data.job_id:
        job_result = await db.execute(select(Job).where(Job.id == data.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    app = Application(
        job_id=data.job_id,
        status=data.status,
        notes=data.notes,
        applied_via=data.applied_via,
    )
    db.add(app)
    await db.flush()

    # Add log entry
    details = f"Application logged"
    if job:
        details = f"Application logged for {job.title} at {job.company}"
    log = ApplicationLog(application_id=app.id, action="created", details=details)
    db.add(log)
    await db.commit()

    await db.refresh(app, attribute_names=["logs", "job"])
    return _app_to_response(app)


@router.patch("/{app_id}", response_model=ApplicationResponse)
async def update_application(app_id: uuid.UUID, data: ApplicationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.logs), selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    changes = []
    if data.status is not None and data.status != app.status:
        changes.append(f"status: {app.status} → {data.status}")
        app.status = data.status
    if data.notes is not None:
        app.notes = data.notes
        changes.append("notes updated")

    if changes:
        log = ApplicationLog(
            application_id=app.id,
            action="updated",
            details=", ".join(changes),
        )
        db.add(log)

    await db.flush()
    await db.refresh(app, attribute_names=["logs", "job"])
    return _app_to_response(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(app)
    await db.commit()


@router.post("/{app_id}/archive", response_model=ApplicationResponse)
async def archive_application(app_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.logs), selectinload(Application.job))
        .where(Application.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = ApplicationStatus.ARCHIVED
    log = ApplicationLog(application_id=app.id, action="archived", details="Application archived")
    db.add(log)
    await db.flush()
    await db.refresh(app, attribute_names=["logs", "job"])
    return _app_to_response(app)


@router.post("/bulk-delete", status_code=204)
async def bulk_delete_applications(data: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application).where(Application.id.in_(data.ids))
    )
    apps = result.scalars().all()
    for app in apps:
        await db.delete(app)
    await db.commit()
