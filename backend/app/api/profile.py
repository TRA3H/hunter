import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.profile import Education, UserProfile, WorkExperience
from app.schemas.profile import (
    EducationCreate,
    EducationResponse,
    ProfileResponse,
    ProfileUpdate,
    WorkExperienceCreate,
    WorkExperienceResponse,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")


async def _get_or_create_profile(db: AsyncSession) -> UserProfile:
    result = await db.execute(
        select(UserProfile)
        .options(selectinload(UserProfile.education), selectinload(UserProfile.work_experience))
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        await db.flush()
        await db.refresh(profile, attribute_names=["education", "work_experience"])
    return profile


@router.get("", response_model=ProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)
    return ProfileResponse.model_validate(profile)


@router.put("", response_model=ProfileResponse)
async def update_profile(data: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.flush()
    await db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.post("/resume", response_model=ProfileResponse)
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"resume_{profile.id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    profile.resume_filename = file.filename or ""
    profile.resume_path = filepath

    await db.flush()
    await db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.post("/education", response_model=EducationResponse, status_code=201)
async def add_education(data: EducationCreate, db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)
    edu = Education(profile_id=profile.id, **data.model_dump())
    db.add(edu)
    await db.flush()
    await db.refresh(edu)
    return EducationResponse.model_validate(edu)


@router.delete("/education/{edu_id}", status_code=204)
async def delete_education(edu_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Education).where(Education.id == edu_id))
    edu = result.scalar_one_or_none()
    if not edu:
        raise HTTPException(status_code=404, detail="Education entry not found")
    await db.delete(edu)
    await db.commit()


@router.post("/experience", response_model=WorkExperienceResponse, status_code=201)
async def add_experience(data: WorkExperienceCreate, db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)
    exp = WorkExperience(profile_id=profile.id, **data.model_dump())
    db.add(exp)
    await db.flush()
    await db.refresh(exp)
    return WorkExperienceResponse.model_validate(exp)


@router.delete("/experience/{exp_id}", status_code=204)
async def delete_experience(exp_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkExperience).where(WorkExperience.id == exp_id))
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience entry not found")
    await db.delete(exp)
    await db.commit()
