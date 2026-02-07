import uuid

import pytest

from app.models.job import Job
from app.models.profile import UserProfile


@pytest.fixture
def sample_profile():
    return UserProfile(
        id=uuid.uuid4(),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        website_url="https://janedoe.dev",
        us_citizen=True,
        sponsorship_needed=False,
        desired_title="Senior Software Engineer",
        desired_locations="San Francisco, CA, New York, NY, Remote",
        min_salary=150000,
        remote_preference="remote",
    )


@pytest.fixture
def sample_job():
    return Job(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        title="Senior Software Engineer",
        company="TechCorp",
        location="San Francisco, CA (Remote)",
        url="https://example.com/jobs/123",
        description="""
        We are looking for a Senior Software Engineer to join our team.
        Requirements:
        - 5+ years of experience with Python, TypeScript, or Go
        - Experience with React, FastAPI, or similar frameworks
        - Strong understanding of distributed systems
        - Experience with PostgreSQL, Redis, and Docker
        - Excellent communication skills

        Benefits:
        - Competitive salary $150,000 - $200,000
        - Remote-first culture
        - Health, dental, vision insurance
        - 401k matching
        """,
        dedup_hash="abc123",
        match_score=0.0,
    )


@pytest.fixture
def sample_raw_jobs():
    return [
        {
            "title": "Backend Engineer",
            "company": "StartupCo",
            "location": "Remote",
            "url": "https://example.com/jobs/1",
            "salary": "$120,000 - $160,000",
            "description": "Build APIs with Python and FastAPI.",
            "posted_date": "2025-01-15T00:00:00",
        },
        {
            "title": "Frontend Developer",
            "company": "WebCo",
            "location": "New York, NY",
            "url": "https://example.com/jobs/2",
            "salary": "$100K - $140K",
            "description": "Build UIs with React and TypeScript.",
        },
        {
            "title": "DevOps Engineer",
            "company": "CloudCo",
            "location": "San Francisco, CA",
            "url": "https://example.com/jobs/3",
            "salary": "",
            "description": "Manage infrastructure with Docker and Kubernetes.",
        },
    ]
