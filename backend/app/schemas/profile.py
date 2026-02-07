import uuid
from datetime import datetime

from pydantic import BaseModel


class EducationCreate(BaseModel):
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    gpa: str = ""
    graduation_year: int | None = None


class EducationResponse(BaseModel):
    id: uuid.UUID
    school: str
    degree: str
    field_of_study: str
    gpa: str
    graduation_year: int | None

    model_config = {"from_attributes": True}


class WorkExperienceCreate(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class WorkExperienceResponse(BaseModel):
    id: uuid.UUID
    company: str
    title: str
    start_date: str
    end_date: str
    description: str

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    us_citizen: bool | None = None
    sponsorship_needed: bool | None = None
    veteran_status: str | None = None
    disability_status: str | None = None
    gender: str | None = None
    ethnicity: str | None = None
    cover_letter_template: str | None = None
    desired_title: str | None = None
    desired_locations: str | None = None
    min_salary: int | None = None
    remote_preference: str | None = None


class ProfileResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str
    linkedin_url: str
    website_url: str
    us_citizen: bool | None
    sponsorship_needed: bool | None
    veteran_status: str
    disability_status: str
    gender: str
    ethnicity: str
    resume_filename: str
    cover_letter_template: str
    desired_title: str
    desired_locations: str
    min_salary: int | None
    remote_preference: str
    education: list[EducationResponse]
    work_experience: list[WorkExperienceResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
