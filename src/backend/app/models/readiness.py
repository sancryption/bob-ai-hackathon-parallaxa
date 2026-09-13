"""ORM models for the Readiness Assessment domain.

Tables
------
ctd_requirements        – versioned catalog of CTD regulatory requirements
dossier_sections        – sections found / extracted from an uploaded dossier
readiness_assessments   – one assessment result per job
requirement_mappings    – links each requirement to a dossier section (or gap)
gaps                    – concrete gaps between a requirement and the dossier

NOTE: The prototype CTD catalog bundled with this codebase is a representative
reference structure covering all five CTD modules.  It is NOT a complete,
jurisdiction-specific regulatory checklist.  Always consult current ICH,
FDA, EMA, or other applicable authority guidance before use in a regulatory
submission context.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# CtdRequirement  (versioned catalog)
# ---------------------------------------------------------------------------


class CtdRequirement(SQLModel, table=True):
    """One entry in the CTD regulatory requirements catalog.

    requirement_id is the stable business key, e.g. 'CTD-3.2.S.1'.
    catalog_version allows the catalog to evolve without breaking existing
    assessments — each assessment records which catalog_version it used.
    """

    __tablename__ = "ctd_requirements"
    __table_args__ = (
        Index("ix_ctd_requirements_requirement_id", "requirement_id"),
        Index("ix_ctd_requirements_catalog_version", "catalog_version"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Stable human-readable business key
    requirement_id: str = Field(max_length=64, nullable=False)
    catalog_version: str = Field(default="0.1.0", max_length=32)
    module: str = Field(max_length=8)          # "1" … "5"
    section: str = Field(max_length=32)        # e.g. "3.2.S.1"
    title: str = Field(max_length=512)
    description: str = Field(max_length=4096)
    is_mandatory: bool = Field(default=True)
    guidance_ref: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# DossierSection
# ---------------------------------------------------------------------------


class SectionStatus(str, Enum):
    complete = "complete"
    missing = "missing"
    ambiguous = "ambiguous"
    optional = "optional"
    review_needed = "review_needed"


class DossierSection(SQLModel, table=True):
    """One section extracted from an uploaded dossier document."""

    __tablename__ = "dossier_sections"
    __table_args__ = (
        Index("ix_dossier_sections_project_id", "project_id"),
        Index("ix_dossier_sections_upload_id", "upload_id"),
        Index("ix_dossier_sections_assessment_id", "assessment_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    upload_id: int = Field(foreign_key="uploads.id", nullable=False)
    assessment_id: Optional[int] = Field(
        default=None, foreign_key="readiness_assessments.id"
    )
    # Stable business key supplied by the dossier parser, e.g. "SEC-3.2.S.1"
    section_id: str = Field(max_length=64)
    module: str = Field(max_length=8)
    title: str = Field(max_length=512)
    content_summary: Optional[str] = Field(default=None, max_length=4096)
    status: SectionStatus = Field(default=SectionStatus.review_needed)
    page_ref: Optional[str] = Field(default=None, max_length=128)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# ReadinessAssessment
# ---------------------------------------------------------------------------


class ReviewStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    approved = "approved"
    rejected = "rejected"


class ReadinessAssessment(SQLModel, table=True):
    """Aggregate readiness result for one project / job execution."""

    __tablename__ = "readiness_assessments"
    __table_args__ = (
        Index("ix_readiness_assessments_project_id", "project_id"),
        Index("ix_readiness_assessments_job_id", "job_id"),
        Index("ix_readiness_assessments_assessment_id", "id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    job_id: int = Field(foreign_key="jobs.id", nullable=False)
    upload_id: Optional[int] = Field(default=None, foreign_key="uploads.id")
    overall_score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(max_length=4096)
    # JSON-serialised list of ModuleScore objects
    module_scores_json: Optional[str] = Field(default=None)
    review_status: ReviewStatus = Field(default=ReviewStatus.not_started)
    algorithm_version: str = Field(default="0.1.0", max_length=32)
    catalog_version: str = Field(default="0.1.0", max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# RequirementMapping
# ---------------------------------------------------------------------------


class RequirementMapping(SQLModel, table=True):
    """Links one CtdRequirement to zero or one DossierSection within an assessment."""

    __tablename__ = "requirement_mappings"
    __table_args__ = (
        Index("ix_requirement_mappings_assessment_id", "assessment_id"),
        Index("ix_requirement_mappings_requirement_id", "requirement_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_id: int = Field(
        foreign_key="readiness_assessments.id", nullable=False
    )
    # Business-key reference to ctd_requirements.requirement_id
    requirement_id: str = Field(max_length=64)
    # FK to dossier_sections; NULL means requirement has no matching section
    dossier_section_id: Optional[int] = Field(
        default=None, foreign_key="dossier_sections.id"
    )
    status: SectionStatus
    notes: Optional[str] = Field(default=None, max_length=2048)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Gap
# ---------------------------------------------------------------------------


class GapSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Gap(SQLModel, table=True):
    """A concrete gap between a requirement and the uploaded dossier."""

    __tablename__ = "gaps"
    __table_args__ = (
        Index("ix_gaps_assessment_id", "assessment_id"),
        Index("ix_gaps_requirement_id", "requirement_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_id: int = Field(
        foreign_key="readiness_assessments.id", nullable=False
    )
    # Stable business key, e.g. "GAP-001"
    gap_id: str = Field(max_length=64)
    # Business-key reference to ctd_requirements.requirement_id
    requirement_id: str = Field(max_length=64)
    dossier_section_id: Optional[int] = Field(
        default=None, foreign_key="dossier_sections.id"
    )
    description: str = Field(max_length=4096)
    severity: GapSeverity
    recommendation: str = Field(max_length=4096)
    review_status: ReviewStatus = Field(default=ReviewStatus.not_started)
    notes: Optional[str] = Field(default=None, max_length=2048)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
