import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.application import Application
from app.models.profile import UserProfile

logger = logging.getLogger(__name__)


def _build_profile_summary(profile: UserProfile) -> str:
    """Build a text summary of the user's profile for the AI."""
    parts = [f"Name: {profile.first_name} {profile.last_name}"]

    if profile.desired_title:
        parts.append(f"Desired role: {profile.desired_title}")

    if profile.work_experience:
        parts.append("\nWork Experience:")
        for exp in profile.work_experience:
            parts.append(f"  - {exp.title} at {exp.company} ({exp.start_date} - {exp.end_date})")
            if exp.description:
                parts.append(f"    {exp.description[:300]}")

    if profile.education:
        parts.append("\nEducation:")
        for edu in profile.education:
            parts.append(f"  - {edu.degree} in {edu.field_of_study} from {edu.school} ({edu.graduation_year})")

    return "\n".join(parts)


async def generate_answers(application: Application, db: AsyncSession) -> dict:
    """Use Claude API to generate answers for free-text application questions.

    Returns a dict mapping field_name to suggested answer.
    """
    if not settings.anthropic_api_key:
        logger.warning("Anthropic API key not configured, cannot generate AI answers")
        return {}

    # Load profile
    result = await db.execute(
        select(UserProfile)
        .options(selectinload(UserProfile.work_experience), selectinload(UserProfile.education))
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        logger.warning("No user profile found, cannot generate AI answers")
        return {}

    # Get the fields that need input
    fields = application.form_fields or []
    questions = [f for f in fields if f.get("status") == "needs_input" and f.get("field_type") in ("text", "textarea")]

    if not questions:
        return {}

    profile_summary = _build_profile_summary(profile)
    job_description = application.job.description if application.job else ""

    # Build prompt for each question
    question_list = "\n".join(
        f'{i+1}. Field "{q["label"]}" (type: {q["field_type"]}): Please provide a response.'
        for i, q in enumerate(questions)
    )

    prompt = f"""You are helping a job applicant fill out an application form. Based on the applicant's profile and the job description, provide concise, professional answers to the following form questions.

APPLICANT PROFILE:
{profile_summary}

JOB DESCRIPTION:
{job_description[:3000]}

QUESTIONS TO ANSWER:
{question_list}

For each question, provide a natural, honest, and professional response. If it's a "Why do you want to work here?" type question, reference specific aspects of the company/role from the job description. Keep answers concise but substantive (2-4 sentences for short text, 1-2 paragraphs for textarea fields).

Respond in this exact format for each question:
ANSWER_1: [your answer]
ANSWER_2: [your answer]
...etc"""

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text if response.content else ""

        # Parse answers
        answers = {}
        for i, question in enumerate(questions):
            marker = f"ANSWER_{i+1}:"
            start = response_text.find(marker)
            if start == -1:
                continue

            start += len(marker)
            # Find next answer marker or end
            next_marker = f"ANSWER_{i+2}:"
            end = response_text.find(next_marker, start)
            if end == -1:
                end = len(response_text)

            answer = response_text[start:end].strip()
            answers[question["field_name"]] = answer

        logger.info("Generated AI answers for %d questions", len(answers))
        return answers

    except Exception:
        logger.exception("Failed to generate AI answers")
        return {}
