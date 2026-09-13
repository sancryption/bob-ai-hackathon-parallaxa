"""Pydantic request/response schemas shared across the application.

These types are the single source of truth for API contracts.  They are
intentionally kept separate from the ORM models so that the API surface can
evolve independently of the database schema.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Generic envelope
# ---------------------------------------------------------------------------

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class ErrorEnvelope(BaseModel):
    """Standard error response body returned for all 4xx / 5xx responses."""

    error: ErrorDetail


class OkEnvelope(BaseModel, Generic[DataT]):
    """Standard success response body wrapping any payload."""

    data: DataT


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectStatus(str, Enum):
    draft = "draft"
    processing = "processing"
    ready = "ready"
    error = "error"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    items: List[ProjectRead]
    total: int


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class UploadStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class UploadRead(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: str
    status: UploadStatus
    created_at: datetime

    model_config = {"from_attributes": True}


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


class JobRead(BaseModel):
    id: int
    project_id: int
    job_type: JobType
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class SignalSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SignalRead(BaseModel):
    id: int
    project_id: int
    job_id: int
    title: str
    description: str
    severity: SignalSeverity
    source_ref: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalList(BaseModel):
    items: List[SignalRead]
    total: int


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------


class RequirementRead(BaseModel):
    id: int
    project_id: int
    text: str
    source_ref: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequirementList(BaseModel):
    items: List[RequirementRead]
    total: int


# ---------------------------------------------------------------------------
# Gap
# ---------------------------------------------------------------------------


class GapSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class GapRead(BaseModel):
    id: int
    project_id: int
    requirement_id: int
    description: str
    severity: GapSeverity
    created_at: datetime

    model_config = {"from_attributes": True}


class GapList(BaseModel):
    items: List[GapRead]
    total: int


# ---------------------------------------------------------------------------
# Readiness Assessment
# ---------------------------------------------------------------------------


class ReadinessAssessmentRead(BaseModel):
    id: int
    project_id: int
    job_id: int
    score: float = Field(ge=0.0, le=1.0)
    summary: str
    gaps: List[GapRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}
