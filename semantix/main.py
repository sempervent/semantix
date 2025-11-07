"""Main application bootstrap: FastAPI + NiceGUI."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import app as ng_app, ui

from semantix.api.routes import api_router
from semantix.api.ws import ws_endpoint
from semantix.config import settings
from semantix.ingest.watcher import start_watcher
from semantix.store.redis import close_redis, get_redis
from semantix.ui.app import build_ui
from semantix.utils.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    logger.info("Starting Semantix application...")
    
    # Initialize Redis connection
    await get_redis()
    logger.info("Redis connection established")
    
    # Start file watcher
    asyncio.create_task(start_watcher())
    logger.info("File watcher started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Semantix application...")
    await close_redis()
    logger.info("Redis connection closed")


# Create FastAPI app
fastapi_app = FastAPI(
    title="Semantix",
    description="Semantic labeling and training pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# Include API routes
fastapi_app.include_router(api_router, prefix="/api", tags=["api"])

# Add WebSocket endpoint
fastapi_app.add_api_websocket_route("/ws", ws_endpoint)


# Build NiceGUI UI
build_ui()

# Mount FastAPI app under /backend
ng_app.mount("/backend", fastapi_app)

# Export NiceGUI app as main ASGI app
app = ng_app

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "semantix.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info",
    )

