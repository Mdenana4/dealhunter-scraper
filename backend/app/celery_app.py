from celery import Celery
from app.config import settings

celery_app = Celery(
    "dealhunter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scrape-deals-every-30-minutes": {
            "task": "app.tasks.scrape_deals",
            "schedule": 1800.0,
        },
    },
)
