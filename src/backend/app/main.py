"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.session import create_db_and_tables
from app.routers import health, projects
from app.routers import jobs as jobs_router
from app.routers import signals as signals_router
from app.routers import readiness as readiness_router
from app.schemas import ErrorDetail, ErrorEnvelope


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        create_db_and_tables()
        yield

    app = FastAPI(
        title="SafetyReady API",
        version="0.2.0",
        description=(
            "SafetyReady — deterministic pharmacovigilance signal detection "
            "and submission readiness assessment."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS — allow the local Vite dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler → consistent error envelope
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected error occurred.",
                )
            ).model_dump(),
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(jobs_router.router, prefix="/api")
    app.include_router(signals_router.router, prefix="/api")
    app.include_router(readiness_router.router, prefix="/api")

    return app


app = create_app()
