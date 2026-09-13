"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.session import create_db_and_tables
from app.routers import health, projects
from app.schemas import ErrorDetail, ErrorEnvelope


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        create_db_and_tables()
        yield

    app = FastAPI(
        title="SafetyReady API",
        version="0.1.0",
        description="SafetyReady — submission readiness and signal detection.",
        lifespan=lifespan,
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

    return app


app = create_app()
