import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hr_minds.settings.logging import setup_logging
from hr_minds.settings.routers import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the app's startup and shutdown.

    - Code before `yield` runs once when the server starts.
    - `yield` lets the server handle requests.
    - Code after `yield` runs once when the server stops.
    """
    setup_logging()

    logger.info("API Service has successfully started up and is ready for requests")
    yield
    logger.info("API Service is shutting down gracefully")


app = FastAPI(lifespan=lifespan)

# Mount the single centralized router
app.include_router(api_router)
