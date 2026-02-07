import asyncio
import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import boards, jobs, profile, autoapply, websocket
from app.api.websocket import ws_listener
from app.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.log_level)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Hunter - Job Search Automation",
    description="Automated job searching, monitoring, and application submission",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads/screenshots
import os
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "screenshots"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(boards.router)
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(autoapply.router)
app.include_router(websocket.router)


@app.on_event("startup")
async def startup():
    logger.info("Hunter backend starting up")
    # Start WebSocket Redis listener
    asyncio.create_task(ws_listener())


@app.on_event("shutdown")
async def shutdown():
    logger.info("Hunter backend shutting down")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
