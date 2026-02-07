import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.board import JobBoard
from app.schemas.board import BoardCreate, BoardListResponse, BoardResponse, BoardUpdate

router = APIRouter(prefix="/api/boards", tags=["boards"])


@router.get("", response_model=BoardListResponse)
async def list_boards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobBoard).order_by(JobBoard.created_at.desc()))
    boards = result.scalars().all()
    return BoardListResponse(boards=[BoardResponse.model_validate(b) for b in boards], total=len(boards))


@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(board_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobBoard).where(JobBoard.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return BoardResponse.model_validate(board)


@router.post("", response_model=BoardResponse, status_code=201)
async def create_board(data: BoardCreate, db: AsyncSession = Depends(get_db)):
    board = JobBoard(
        name=data.name,
        url=data.url,
        scan_interval_minutes=data.scan_interval_minutes,
        enabled=data.enabled,
        keyword_filters=data.keyword_filters,
        scraper_config=data.scraper_config.model_dump(),
    )
    db.add(board)
    await db.flush()
    await db.refresh(board)
    return BoardResponse.model_validate(board)


@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(board_id: uuid.UUID, data: BoardUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobBoard).where(JobBoard.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    update_data = data.model_dump(exclude_unset=True)
    if "scraper_config" in update_data and update_data["scraper_config"] is not None:
        update_data["scraper_config"] = update_data["scraper_config"].model_dump() if hasattr(update_data["scraper_config"], "model_dump") else update_data["scraper_config"]

    for field, value in update_data.items():
        setattr(board, field, value)

    await db.flush()
    await db.refresh(board)
    return BoardResponse.model_validate(board)


@router.delete("/{board_id}", status_code=204)
async def delete_board(board_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobBoard).where(JobBoard.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    await db.delete(board)


@router.post("/{board_id}/scan", response_model=dict)
async def trigger_scan(board_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobBoard).where(JobBoard.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    from app.tasks.scan_tasks import scan_board_task
    task = scan_board_task.delay(str(board_id))
    return {"task_id": task.id, "message": f"Scan started for {board.name}"}
