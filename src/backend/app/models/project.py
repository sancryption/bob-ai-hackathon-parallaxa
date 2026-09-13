"""ORM models for the Project domain."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ProjectStatus(str, Enum):
    draft = "draft"
    processing = "processing"
    ready = "ready"
    error = "error"


class ProjectBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: ProjectStatus = Field(default=ProjectStatus.draft)


class Project(ProjectBase, table=True):
    """Persisted project row."""

    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
