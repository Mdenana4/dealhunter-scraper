import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import init_db, check_db_health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DealHunter API...")
    await init_db()
    logger.info("Database initialized successfully")
    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    db_ok = await check_db_health()
    if not db_ok:
        logger.error("Database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": "Database connection failed"},
        )
    return {"status": "healthy", "database": "connected"}


@app.get("/")
async def root():
    return {"message": "DealHunter API", "version": settings.api_version}
