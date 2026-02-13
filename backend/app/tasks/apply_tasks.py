import asyncio
import logging
from datetime import datetime, timezone

from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.application import Application, ApplicationLog, ApplicationStatus
from app.models.job import Job
from app.models.profile import UserProfile
from app.services.autofill import (
    analyze_form_fields,
    fill_form_fields,
    has_captcha,
    needs_human_review,
    take_screenshot,
)
from app.services.notifier import notify_application_needs_review
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


def _get_async_session() -> async_sessionmaker:
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _add_log(db: AsyncSession, app_id: str, action: str, details: str, screenshot: str = ""):
    log = ApplicationLog(
        application_id=app_id,
        action=action,
        details=details,
        screenshot_path=screenshot,
    )
    db.add(log)
    await db.flush()


async def _find_apply_button(page):
    """Look for a visible 'Apply' button on job description pages.
    Many job boards (Ashby, Greenhouse, Lever, etc.) show the job description
    first and require clicking an 'Apply' button to reach the actual form."""
    apply_selectors = [
        'a:has-text("Apply for this Job")',
        'button:has-text("Apply for this Job")',
        'a:has-text("Apply Now")',
        'button:has-text("Apply Now")',
        'a:has-text("Apply for this Position")',
        'button:has-text("Apply for this Position")',
        'a:has-text("Apply to this Job")',
        'button:has-text("Apply to this Job")',
        'a:has-text("Apply")',
        'button:has-text("Apply")',
        '[data-testid="apply-button"]',
        '.apply-button',
        '#apply-button',
    ]
    for selector in apply_selectors:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                return el
        except Exception:
            continue
    return None


async def _run_auto_apply(app_id: str):
    """Execute the auto-apply process for an application."""
    session_factory = _get_async_session()

    async with session_factory() as db:
        result = await db.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.id == app_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            logger.error("Application %s not found", app_id)
            return

        job = application.job
        if not job:
            logger.error("Job not found for application %s", app_id)
            application.status = ApplicationStatus.FAILED
            application.error_message = "Associated job not found"
            await db.commit()
            return

        # Load profile
        profile_result = await db.execute(
            select(UserProfile)
            .options(
                selectinload(UserProfile.education),
                selectinload(UserProfile.work_experience),
            )
            .limit(1)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            application.status = ApplicationStatus.FAILED
            application.error_message = "User profile not found. Please set up your profile first."
            await _add_log(db, str(app_id), "failed", "No user profile found")
            await db.commit()
            return

        application.status = ApplicationStatus.IN_PROGRESS
        await _add_log(db, str(app_id), "started", f"Starting auto-apply for {job.title} at {job.company}")
        await db.commit()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=settings.playwright_headless)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                # Navigate to application URL
                await _add_log(db, str(app_id), "navigating", f"Opening {job.url}")
                await db.commit()

                await page.goto(job.url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)  # Extra wait for JS rendering

                # Try to click through to the application form if we're on
                # a job description page with an "Apply" button/tab
                apply_btn = await _find_apply_button(page)
                if apply_btn:
                    await _add_log(db, str(app_id), "clicking_apply", "Found apply button, clicking through to application form")
                    await db.commit()
                    try:
                        await apply_btn.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await page.wait_for_timeout(2000)
                    except Exception as e:
                        logger.warning("Failed to click apply button: %s", e)

                screenshot_path = await take_screenshot(page, "initial")
                await _add_log(db, str(app_id), "page_loaded", "Application page loaded", screenshot_path)
                await db.commit()

                # Check for visible CAPTCHA widgets
                if await has_captcha(page):
                    application.status = ApplicationStatus.NEEDS_REVIEW
                    application.screenshot_path = screenshot_path
                    application.current_page_url = page.url
                    application.form_fields = [{"field_name": "captcha", "field_type": "captcha", "label": "CAPTCHA detected", "value": "", "confidence": 0, "status": "needs_input", "options": []}]
                    await _add_log(db, str(app_id), "captcha_detected", "CAPTCHA detected, pausing for human review", screenshot_path)
                    await db.commit()

                    notify_application_needs_review(str(app_id), job.title, job.company)
                    _broadcast_status(str(app_id), "needs_review", "CAPTCHA detected")
                    await browser.close()
                    return

                # Analyze form fields
                await _add_log(db, str(app_id), "analyzing", "Analyzing form fields")
                await db.commit()

                fields = await analyze_form_fields(page, profile)
                logger.info("Found %d form fields for application %s", len(fields), app_id)

                # Attempt to fill fields
                await _add_log(db, str(app_id), "filling", f"Attempting to fill {len(fields)} fields")
                await db.commit()

                filled_fields = await fill_form_fields(page, fields)

                # Upload resume if there's a file input
                for field in filled_fields:
                    if field["field_type"] == "file" and profile.resume_path:
                        import os
                        if os.path.exists(profile.resume_path):
                            field["value"] = profile.resume_filename or os.path.basename(profile.resume_path)
                            field["_resume_path"] = profile.resume_path
                            selector = field.get("_selector", "")
                            if selector:
                                try:
                                    elem = await page.query_selector(selector)
                                    if elem:
                                        await elem.set_input_files(profile.resume_path)
                                        field["status"] = "filled"
                                        await _add_log(db, str(app_id), "resume_uploaded", "Resume uploaded")
                                except Exception as e:
                                    logger.warning("Failed to upload resume: %s", e)
                                    field["status"] = "needs_input"

                # Take screenshot after filling
                screenshot_path = await take_screenshot(page, "filled")
                await _add_log(db, str(app_id), "fields_filled", "Form fields processed", screenshot_path)

                # Clean fields for storage (remove internal _selector)
                clean_fields = [{k: v for k, v in f.items() if not k.startswith("_")} for f in filled_fields]

                # Check if human review is needed
                if needs_human_review(filled_fields):
                    application.status = ApplicationStatus.NEEDS_REVIEW
                    application.form_fields = clean_fields
                    application.screenshot_path = screenshot_path
                    application.current_page_url = page.url
                    await _add_log(db, str(app_id), "needs_review", "Some fields need human input, pausing for review", screenshot_path)
                    await db.commit()

                    notify_application_needs_review(str(app_id), job.title, job.company)
                    _broadcast_status(str(app_id), "needs_review", "Needs human review")
                else:
                    # All fields filled with high confidence — still don't submit, wait for user
                    application.status = ApplicationStatus.NEEDS_REVIEW
                    application.form_fields = clean_fields
                    application.screenshot_path = screenshot_path
                    application.current_page_url = page.url
                    await _add_log(db, str(app_id), "ready_for_review", "All fields filled, awaiting user confirmation before submit", screenshot_path)
                    await db.commit()

                    _broadcast_status(str(app_id), "needs_review", "Ready for review")

                await browser.close()

        except Exception as e:
            logger.exception("Auto-apply failed for application %s", app_id)
            application.status = ApplicationStatus.FAILED
            application.error_message = str(e)[:500]
            await _add_log(db, str(app_id), "error", f"Auto-apply failed: {str(e)[:300]}")
            await db.commit()

            _broadcast_status(str(app_id), "failed", str(e)[:200])


async def _run_resume_apply(app_id: str):
    """Resume an application after user review — fill reviewed fields and submit."""
    session_factory = _get_async_session()

    async with session_factory() as db:
        result = await db.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.id == app_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            logger.error("Application %s not found for resume", app_id)
            return

        if application.status != ApplicationStatus.READY_TO_SUBMIT:
            logger.warning("Application %s not in READY_TO_SUBMIT state", app_id)
            return

        job = application.job
        fields = application.form_fields or []

        # Load profile for resume path
        profile_result = await db.execute(select(UserProfile).limit(1))
        profile = profile_result.scalar_one_or_none()

        application.status = ApplicationStatus.IN_PROGRESS
        await _add_log(db, str(app_id), "resuming", "Resuming application with user-reviewed fields")
        await db.commit()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=settings.playwright_headless)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                await page.goto(application.current_page_url or job.url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Fill all fields with user-reviewed values
                await _fill_page_fields(page, fields, profile)

                # Take final screenshot before submit
                screenshot_path = await take_screenshot(page, "pre_submit")
                await _add_log(db, str(app_id), "fields_filled", "All reviewed fields filled", screenshot_path)

                # Look for and click submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Submit")',
                    'button:has-text("Apply")',
                    'button:has-text("Send")',
                ]
                submitted = False
                for sel in submit_selectors:
                    try:
                        btn = await page.query_selector(sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            submitted = True
                            break
                    except Exception:
                        continue

                if submitted:
                    await page.wait_for_timeout(3000)
                    screenshot_path = await take_screenshot(page, "submitted")
                    application.status = ApplicationStatus.SUBMITTED
                    application.submitted_at = datetime.now(timezone.utc)
                    application.screenshot_path = screenshot_path
                    await _add_log(db, str(app_id), "submitted", "Application submitted successfully", screenshot_path)
                    _broadcast_status(str(app_id), "submitted", "Application submitted")
                else:
                    application.status = ApplicationStatus.NEEDS_REVIEW
                    await _add_log(db, str(app_id), "submit_failed", "Could not find submit button, needs manual submission")
                    _broadcast_status(str(app_id), "needs_review", "Submit button not found")

                await db.commit()
                await browser.close()

        except Exception as e:
            logger.exception("Resume apply failed for application %s", app_id)
            application.status = ApplicationStatus.FAILED
            application.error_message = str(e)[:500]
            await _add_log(db, str(app_id), "error", f"Resume apply failed: {str(e)[:300]}")
            await db.commit()

            _broadcast_status(str(app_id), "failed", str(e)[:200])


async def _fill_page_fields(page, fields: list[dict], profile: UserProfile | None):
    """Fill form fields on a page. Shared by _run_resume_apply and _run_open_browser."""
    import os

    for field in fields:
        if not field.get("value") or not field.get("field_name"):
            continue
        try:
            selector = f"[name='{field['field_name']}']"
            elem = await page.query_selector(selector)
            if not elem:
                selector = f"#{field['field_name']}"
                elem = await page.query_selector(selector)

            if elem:
                if field["field_type"] == "select":
                    await elem.select_option(label=field["value"])
                elif field["field_type"] == "checkbox":
                    is_checked = await elem.is_checked()
                    should_check = field["value"].lower() in ("yes", "true", "1")
                    if is_checked != should_check:
                        await elem.click()
                elif field["field_type"] == "file":
                    resume_path = profile.resume_path if profile else ""
                    if resume_path and os.path.exists(resume_path):
                        await elem.set_input_files(resume_path)
                else:
                    await elem.fill("")
                    await elem.fill(field["value"])
        except Exception as e:
            logger.warning("Failed to fill field %s: %s", field["field_name"], e)


async def _run_open_browser(app_id: str):
    """Open a headed browser with form fields pre-filled for the user."""
    session_factory = _get_async_session()

    async with session_factory() as db:
        result = await db.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.id == app_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            logger.error("Application %s not found for open-browser", app_id)
            return

        job = application.job
        fields = application.form_fields or []

        # Load profile for resume
        profile_result = await db.execute(select(UserProfile).limit(1))
        profile = profile_result.scalar_one_or_none()

        await _add_log(db, str(app_id), "browser_opened", "Opening headed browser with pre-filled form data")
        await db.commit()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                url = application.current_page_url or (job.url if job else None)
                if not url:
                    logger.error("No URL available for application %s", app_id)
                    return

                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Fill stored field values
                await _fill_page_fields(page, fields, profile)

                # Wait for user to close the browser
                disconnected = asyncio.Event()
                browser.on("disconnected", lambda: disconnected.set())
                await disconnected.wait()

            async with session_factory() as db2:
                await _add_log(db2, str(app_id), "browser_closed", "User closed the headed browser")
                await db2.commit()

        except Exception as e:
            logger.exception("Open browser failed for application %s", app_id)
            async with session_factory() as db2:
                await _add_log(db2, str(app_id), "error", f"Open browser failed: {str(e)[:300]}")
                await db2.commit()


def _broadcast_status(app_id: str, status: str, message: str):
    """Broadcast application status update to WebSocket clients."""
    try:
        from app.api.websocket import broadcast_sync
        broadcast_sync("application_update", {
            "application_id": app_id,
            "status": status,
            "message": message,
        })
    except Exception:
        logger.warning("Failed to broadcast status update")


@celery.task(name="app.tasks.apply_tasks.auto_apply_task", bind=True, max_retries=1)
def auto_apply_task(self, app_id: str):
    """Celery task to run auto-apply for an application."""
    try:
        asyncio.run(_run_auto_apply(app_id))
    except Exception as exc:
        logger.exception("Auto-apply task failed for %s", app_id)
        raise self.retry(exc=exc, countdown=30)


@celery.task(name="app.tasks.apply_tasks.resume_apply_task", bind=True, max_retries=1)
def resume_apply_task(self, app_id: str):
    """Celery task to resume an application after user review."""
    try:
        asyncio.run(_run_resume_apply(app_id))
    except Exception as exc:
        logger.exception("Resume apply task failed for %s", app_id)
        raise self.retry(exc=exc, countdown=30)


@celery.task(name="app.tasks.apply_tasks.open_browser_task", bind=True, max_retries=0)
def open_browser_task(self, app_id: str):
    """Celery task to open a headed browser with pre-filled form data."""
    try:
        asyncio.run(_run_open_browser(app_id))
    except Exception:
        logger.exception("Open browser task failed for %s", app_id)
