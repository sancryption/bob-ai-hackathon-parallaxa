"""ORM models for shared infrastructure entities: uploads, jobs, audit_events."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Index
from sqlmodel import Column, Field, SQLModel
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class UploadStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class Upload(SQLModel, table=True):
    """Persisted upload row — one file attached to a project."""

    __tablename__ = "uploads"
    __table_args__ = (
        Index("ix_uploads_project_id", "project_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=128)
    size_bytes: Optional[int] = Field(default=None)
    row_count: Optional[int] = Field(default=None)
    duplicate_count: Optional[int] = Field(default=None)
    status: UploadStatus = Field(default=UploadStatus.pending)
    # Raw storage path / URI; preserved as supplied
    storage_ref: Optional[str] = Field(default=None, max_length=1024)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


class JobType(str, Enum):
    signal_detection = "signal_detection"
    readiness_assessment = "readiness_assessment"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class Job(SQLModel, table=True):
    """Persisted async-job row tracking long-running computations."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    upload_id: Optional[int] = Field(default=None, foreign_key="uploads.id")
    job_type: JobType
    status: JobStatus = Field(default=JobStatus.queued)
    # JSON-serialised progress snapshot while status=running
    progress_json: Optional[str] = Field(default=None)
    # JSON-serialised final result (signal list or assessment id reference)
    result_json: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None, max_length=4096)
    algorithm_version: str = Field(default="0.1.0", max_length=32)
    catalog_version: Optional[str] = Field(default=None, max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------


class AuditEvent(SQLModel, table=True):
    """Immutable audit log: records every state-changing operation."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_project_id", "project_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id")
    job_id: Optional[int] = Field(default=None, foreign_key="jobs.id")
    event_type: str = Field(max_length=128)   # e.g. "project.created"
    actor: Optional[str] = Field(default=None, max_length=255)
    detail_json: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
