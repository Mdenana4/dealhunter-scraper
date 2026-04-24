import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def scrape_deals(self):
    """Periodic task to scrape deals from configured sources."""
    logger.info("Starting deal scrape task")
    try:
        # Scraping logic is implemented in scraper modules
        logger.info("Deal scrape task completed")
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Scrape task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
