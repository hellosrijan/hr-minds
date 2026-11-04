import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hr_minds.settings.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the app's startup and shutdown.

    - Code before `yield` runs once when the server starts.
    - `yield` lets the server handle requests.
    - Code after `yield` runs once when the server stops.
    """
    # Configure logging on startup
    setup_logging()

    # Startup: Executed before the application begins accepting requests
    logger.info("API Service has successfully started up and is ready for requests")
    yield
    # Shutdown: Executed when the application is shutting down (e.g. cleanup, DB disconnects)
    logger.info("API Service is shutting down gracefully")


app = FastAPI(lifespan=lifespan)