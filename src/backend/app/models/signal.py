"""ORM models for the Signal Detection domain.

Tables
------
reports         – one FAERS/source case report per row
drugs           – canonical drug dictionary (deduplicated names)
adverse_events  – canonical adverse-event dictionary (normalised preferred terms)
report_drugs    – M:N link: which drugs appear in which report
report_events   – M:N link: which events appear in which report
drug_event_pairs – pre-aggregated 2×2 contingency table per (drug, event, job)
signals         – detected signals persisted after a job completes
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class Report(SQLModel, table=True):
    """One source-data case report.

    Raw identifier fields are preserved exactly as received so provenance is
    never lost regardless of downstream normalisation.
    """

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_project_id", "project_id"),
        Index("ix_reports_case_id", "case_id"),
        Index("ix_reports_upload_id", "upload_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    upload_id: int = Field(foreign_key="uploads.id", nullable=False)
    # Raw source identifiers — preserved as-is
    primaryid: str = Field(max_length=64)          # FAERS primaryid
    case_id: str = Field(max_length=64)             # FAERS caseid
    case_version: str = Field(default="1", max_length=16)
    # Optional source metadata
    report_date: Optional[str] = Field(default=None, max_length=32)
    age_group: Optional[str] = Field(default=None, max_length=64)
    sex: Optional[str] = Field(default=None, max_length=16)
    reporter_country: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Drug (canonical dictionary)
# ---------------------------------------------------------------------------


class Drug(SQLModel, table=True):
    """Canonical drug entry — deduplicated across all uploads within a project."""

    __tablename__ = "drugs"
    __table_args__ = (
        Index("ix_drugs_project_id", "project_id"),
        Index("ix_drugs_drug_id", "drug_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    # Stable human-readable identifier, e.g. "DRUGALPHA"
    drug_id: str = Field(max_length=255)
    # Normalised display name (upper-cased canonical form)
    name: str = Field(max_length=255)
    # Raw name as it first appeared in the source data
    raw_name: str = Field(max_length=255)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# AdverseEvent (canonical dictionary)
# ---------------------------------------------------------------------------


class AdverseEvent(SQLModel, table=True):
    """Canonical adverse-event preferred term."""

    __tablename__ = "adverse_events"
    __table_args__ = (
        Index("ix_adverse_events_project_id", "project_id"),
        Index("ix_adverse_events_event_id", "event_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    # Stable identifier, e.g. "hepatic_disorder"
    event_id: str = Field(max_length=255)
    # Normalised preferred term
    preferred_term: str = Field(max_length=512)
    # Optional MedDRA code preserved as-supplied
    meddra_code: Optional[str] = Field(default=None, max_length=16)
    # Raw term as it first appeared
    raw_term: str = Field(max_length=512)
    # JSON list of alias raw terms that resolved to this preferred term
    aliases_json: Optional[str] = Field(default=None)
    # Normalisation method: exact_match | alias_lookup | fuzzy
    normalisation_method: str = Field(default="exact_match", max_length=64)
    normalisation_confidence: float = Field(default=1.0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# ReportDrug  (M:N: report → drug)
# ---------------------------------------------------------------------------


class ReportDrug(SQLModel, table=True):
    """Links a report to each drug it mentions."""

    __tablename__ = "report_drugs"
    __table_args__ = (
        Index("ix_report_drugs_report_id", "report_id"),
        Index("ix_report_drugs_drug_id", "drug_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="reports.id", nullable=False)
    drug_id: int = Field(foreign_key="drugs.id", nullable=False)
    # Raw drug name exactly as it appeared in this report row
    raw_name: str = Field(max_length=255)
    role: Optional[str] = Field(default=None, max_length=64)  # e.g. "primary"


# ---------------------------------------------------------------------------
# ReportEvent  (M:N: report → adverse_event)
# ---------------------------------------------------------------------------


class ReportEvent(SQLModel, table=True):
    """Links a report to each adverse event it mentions."""

    __tablename__ = "report_events"
    __table_args__ = (
        Index("ix_report_events_report_id", "report_id"),
        Index("ix_report_events_event_id", "event_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="reports.id", nullable=False)
    event_id: int = Field(foreign_key="adverse_events.id", nullable=False)
    # Raw event term exactly as it appeared in this report row
    raw_term: str = Field(max_length=512)


# ---------------------------------------------------------------------------
# DrugEventPair  (pre-aggregated 2×2 contingency cell per job)
# ---------------------------------------------------------------------------


class DrugEventPair(SQLModel, table=True):
    """Pre-computed 2×2 contingency table for one (drug, event, job) triple."""

    __tablename__ = "drug_event_pairs"
    __table_args__ = (
        Index("ix_drug_event_pairs_job_id", "job_id"),
        Index("ix_drug_event_pairs_drug_id", "drug_id"),
        Index("ix_drug_event_pairs_event_id", "event_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", nullable=False)
    drug_id: int = Field(foreign_key="drugs.id", nullable=False)
    event_id: int = Field(foreign_key="adverse_events.id", nullable=False)
    # 2×2 cells
    a: int = Field(ge=0, description="Drug+Event cases")
    b: int = Field(ge=0, description="Drug+Other-event cases")
    c: int = Field(ge=0, description="Other-drug+Event cases")
    d: int = Field(ge=0, description="Other-drug+Other-event cases")
    # Computed statistics
    prr: float
    prr_lower_ci: Optional[float] = Field(default=None)
    prr_upper_ci: Optional[float] = Field(default=None)
    algorithm_version: str = Field(default="0.1.0", max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class SignalSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Signal(SQLModel, table=True):
    """A detected pharmacovigilance signal persisted after a job completes."""

    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_project_id", "project_id"),
        Index("ix_signals_job_id", "job_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", nullable=False)
    job_id: int = Field(foreign_key="jobs.id", nullable=False)
    drug_event_pair_id: Optional[int] = Field(
        default=None, foreign_key="drug_event_pairs.id"
    )
    title: str = Field(max_length=512)
    description: str = Field(max_length=4096)
    severity: SignalSeverity
    source_ref: Optional[str] = Field(default=None, max_length=512)
    # JSON blob of the full SignalResult schema for this signal
    result_json: Optional[str] = Field(default=None)
    algorithm_version: str = Field(default="0.1.0", max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
