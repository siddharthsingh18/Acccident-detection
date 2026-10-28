import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .api import health_router, incidents_router, media_router, websockets_router, feeds_router
from .services import alert_broadcast_worker, reset_alert_queue, ZmqAlertListener

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("argus.bridge")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Argus FastAPI Bridge...")
    settings.init_directories()

    # Ensure SQLite migrations, WAL mode and busy timeout on active database
    if settings.DATABASE_PATH.exists():
        try:
            from .services.database import apply_migrations
            apply_migrations()
            logger.info("Database schema migrations verified.")
        except Exception as e:
            logger.warning(f"Could not initialize database migrations: {e}")

    loop = asyncio.get_running_loop()

    # Reset queue bound to current loop
    reset_alert_queue()

    # Launch WebSocket broadcaster worker task
    broadcast_task = asyncio.create_task(alert_broadcast_worker())

    # Launch ZeroMQ background listener thread (replaces RunGui.py WorkerThread)
    listener = ZmqAlertListener(loop=loop)
    listener.start()
    app.state.zmq_listener = listener
    app.state.broadcast_task = broadcast_task

    logger.info("Argus FastAPI Bridge initialized successfully.")
    yield

    # Shutdown
    logger.info("Shutting down Argus FastAPI Bridge...")
    if hasattr(app.state, "zmq_listener"):
        app.state.zmq_listener.stop()
        try:
            await asyncio.to_thread(app.state.zmq_listener.join, 1.0)
        except Exception:
            pass
    if hasattr(app.state, "broadcast_task"):
        app.state.broadcast_task.cancel()
        try:
            await app.state.broadcast_task
        except asyncio.CancelledError:
            pass
    logger.info("Argus FastAPI Bridge stopped.")


app = FastAPI(
    title="Argus Road Accident Detection Bridge API",
    description="FastAPI + WebSocket bridge connecting the Argus computer vision pipeline with React frontend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (allows React frontend at http://localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.exceptions import HTTPException as StarletteHTTPException

# Consistent Error Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        content = exc.detail
    else:
        default_code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        content = {
            "code": default_code,
            "message": str(exc.detail),
            "status_code": exc.status_code,
        }
    return JSONResponse(status_code=exc.status_code, content=content)

from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request query, path, or body parameters",
            "details": jsonable_encoder(exc.errors()),
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred while processing the request",
        },
    )

# Register routes
app.include_router(health_router)
app.include_router(incidents_router)
app.include_router(media_router)
app.include_router(websockets_router)
app.include_router(feeds_router)
