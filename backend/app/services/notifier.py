import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _build_job_email_html(jobs: list[dict]) -> str:
    """Build HTML email body for new job notifications."""
    rows = ""
    for job in jobs:
        score_color = "#22c55e" if job["match_score"] >= 70 else "#eab308" if job["match_score"] >= 40 else "#ef4444"
        rows += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <strong>{job["title"]}</strong><br/>
                <span style="color: #6b7280;">{job["company"]} &bull; {job["location"]}</span>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                <span style="background-color: {score_color}; color: white; padding: 4px 8px; border-radius: 12px; font-weight: bold;">
                    {job["match_score"]}%
                </span>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                <a href="{job["url"]}" style="color: #2563eb; text-decoration: none;">Apply &rarr;</a>
            </td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #1e293b; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">🎯 Hunter - New Jobs Found</h2>
            <p style="margin: 8px 0 0 0; color: #94a3b8;">{len(jobs)} new matching job(s) discovered</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead>
                <tr style="background-color: #f8fafc;">
                    <th style="padding: 12px; text-align: left;">Position</th>
                    <th style="padding: 12px; text-align: center;">Match</th>
                    <th style="padding: 12px; text-align: center;">Link</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <div style="padding: 16px; background: #f8fafc; border-radius: 0 0 8px 8px; text-align: center; color: #6b7280;">
            <p style="margin: 0;">Sent by Hunter Job Automation</p>
        </div>
    </body>
    </html>
    """


def send_email_resend(subject: str, html_body: str):
    """Send email using Resend API."""
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured, skipping email")
        return

    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.notification_from_email,
            "to": [settings.notification_to_email],
            "subject": subject,
            "html": html_body,
        })
        logger.info("Email sent via Resend: %s", subject)
    except Exception:
        logger.exception("Failed to send email via Resend, trying SMTP fallback")
        send_email_smtp(subject, html_body)


def send_email_smtp(subject: str, html_body: str):
    """Send email using SMTP as fallback."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP not configured, skipping email notification")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = settings.notification_to_email

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, settings.notification_to_email, msg.as_string())

        logger.info("Email sent via SMTP: %s", subject)
    except Exception:
        logger.exception("Failed to send email via SMTP")


def notify_new_jobs(jobs: list[dict]):
    """Send notification about newly discovered jobs."""
    if not jobs:
        return

    if not settings.notification_to_email:
        logger.info("No notification email configured, skipping")
        return

    subject = f"Hunter: {len(jobs)} new job(s) found"
    html = _build_job_email_html(jobs)

    if settings.resend_api_key:
        send_email_resend(subject, html)
    else:
        send_email_smtp(subject, html)


def notify_application_needs_review(app_id: str, job_title: str, company: str):
    """Notify user that an application needs manual review."""
    if not settings.notification_to_email:
        return

    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #ea580c; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">⚠️ Application Needs Your Review</h2>
        </div>
        <div style="padding: 20px; background: white;">
            <p>Your auto-application for <strong>{job_title}</strong> at <strong>{company}</strong> has been paused
            and needs your input before it can be submitted.</p>
            <p>The bot encountered form fields it couldn't fill automatically. Please review and complete them.</p>
            <p style="text-align: center; margin-top: 20px;">
                <a href="{settings.backend_cors_origins.split(',')[0]}/autoapply"
                   style="background-color: #2563eb; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold;">
                    Review Application
                </a>
            </p>
        </div>
    </body>
    </html>
    """

    subject = f"Hunter: Review needed - {job_title} at {company}"
    if settings.resend_api_key:
        send_email_resend(subject, html)
    else:
        send_email_smtp(subject, html)
