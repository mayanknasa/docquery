import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import Settings
from app.routers import documents
from app.services.llm import build_llm
from app.services.store import build_store

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("docquery")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Build shared clients once at startup, not on every request
        app.state.settings = settings
        app.state.store = build_store(settings)
        app.state.llm = build_llm(settings)
        yield

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        started = time.perf_counter()
        response = await call_next(request)
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
        )
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok"}

    app.include_router(documents.router)
    return app


app = create_app()
