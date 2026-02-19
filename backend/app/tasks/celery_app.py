from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery(
    "hunter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.scan_tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,  # 10 minutes
    task_time_limit=900,  # 15 minutes hard limit
    result_expires=3600,
)

# Beat schedule: check for boards needing scanning every minute
celery.conf.beat_schedule = {
    "check-scan-schedules": {
        "task": "app.tasks.scan_tasks.check_scan_schedules",
        "schedule": 60.0,  # Every minute
    },
}
