"""Pydantic request/response schemas — single source of truth for API contracts.

Kept separate from ORM models so the API surface can evolve independently.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Generic envelope
# ---------------------------------------------------------------------------

DataT = TypeVar("DataT")


class ValidationDetail(BaseModel):
    """Field-level validation error item embedded inside ErrorDetail.loc."""

    loc: List[str]
    msg: str
    type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    validation_errors: Optional[List[ValidationDetail]] = None


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
    size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    duplicate_count: Optional[int] = None
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


class JobProgress(BaseModel):
    """Inline progress snapshot embedded in JobRead while status=running."""

    percent: float = Field(ge=0.0, le=100.0)
    message: str
    step: str


class JobRead(BaseModel):
    id: int
    project_id: int
    job_type: JobType
    status: JobStatus
    progress: Optional[JobProgress] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Event cluster / normalisation provenance
# ---------------------------------------------------------------------------


class NormalizationProvenance(BaseModel):
    """Records how a raw adverse-event string was normalised."""

    raw_term: str
    preferred_term: str
    meddra_code: Optional[str] = None
    method: str  # e.g. "exact_match" | "alias_lookup" | "fuzzy"
    confidence: float = Field(ge=0.0, le=1.0)


class EventCluster(BaseModel):
    """A group of raw event aliases that map to one preferred term."""

    preferred_term: str
    raw_aliases: List[str]
    meddra_code: Optional[str] = None
    case_count: int
    provenances: List[NormalizationProvenance] = []


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class SignalSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ThresholdStatus(str, Enum):
    """Whether the PRR crossed the reporting threshold."""

    below = "below"
    at = "at"
    above = "above"


class SignalSummary(BaseModel):
    """Lightweight signal summary for list views — no per-cell counts."""

    drug: str
    event: str
    prr: float = Field(ge=0.0, description="Proportional Reporting Ratio")
    severity: SignalSeverity
    threshold_status: ThresholdStatus
    rank: int = Field(ge=1)
    total_cases: int


class SignalResult(BaseModel):
    """Full disproportionality result for a single drug–event pair."""

    drug: str
    event: str
    # 2×2 contingency table cells
    a: int = Field(ge=0, description="Drug+Event cases")
    b: int = Field(ge=0, description="Drug+Other-event cases")
    c: int = Field(ge=0, description="Other-drug+Event cases")
    d: int = Field(ge=0, description="Other-drug+Other-event cases")
    prr: float = Field(ge=0.0, description="Proportional Reporting Ratio")
    prr_lower_ci: Optional[float] = Field(
        default=None, description="Lower 95% CI for PRR"
    )
    prr_upper_ci: Optional[float] = Field(
        default=None, description="Upper 95% CI for PRR"
    )
    threshold_status: ThresholdStatus
    severity: SignalSeverity
    rank: int = Field(ge=1)
    algorithm_version: str = Field(
        description="Semantic version of the detection algorithm"
    )
    disclaimer: str = Field(
        description="Regulatory disclaimer text appended to every result"
    )
    event_cluster: Optional[EventCluster] = None


class SignalRead(BaseModel):
    """Persisted signal row returned from the API."""

    id: int
    project_id: int
    job_id: int
    title: str
    description: str
    severity: SignalSeverity
    source_ref: Optional[str] = None
    result: Optional[SignalResult] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalList(BaseModel):
    items: List[SignalRead]
    total: int


class SignalSummaryList(BaseModel):
    """Light summary list for dashboard widgets."""

    items: List[SignalSummary]
    total: int


# ---------------------------------------------------------------------------
# CTD / Dossier
# ---------------------------------------------------------------------------


class CtdModule(str, Enum):
    m1 = "1"
    m2 = "2"
    m3 = "3"
    m4 = "4"
    m5 = "5"


class SectionStatus(str, Enum):
    complete = "complete"
    missing = "missing"
    ambiguous = "ambiguous"
    optional = "optional"
    review_needed = "review_needed"


class CtdRequirement(BaseModel):
    """A single regulatory requirement tied to a CTD module and section."""

    requirement_id: str = Field(description="Stable ID, e.g. 'CTD-3.2.S.1'")
    module: CtdModule
    section: str  # e.g. "3.2.S.1"
    title: str
    description: str
    is_mandatory: bool = True
    guidance_ref: Optional[str] = None  # e.g. ICH guideline reference


class DossierSection(BaseModel):
    """Represents one section of the uploaded dossier."""

    section_id: str
    module: CtdModule
    title: str
    content_summary: Optional[str] = None
    status: SectionStatus
    page_ref: Optional[str] = None  # e.g. "p.42" or document filename


class RequirementMapping(BaseModel):
    """Links one CtdRequirement to zero or one DossierSection."""

    requirement_id: str
    dossier_section_id: Optional[str] = None
    status: SectionStatus
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Readiness Assessment
# ---------------------------------------------------------------------------


class ReviewStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    approved = "approved"
    rejected = "rejected"


class ModuleScore(BaseModel):
    """Readiness score for one CTD module."""

    module: CtdModule
    score: float = Field(ge=0.0, le=1.0)
    complete_count: int
    missing_count: int
    ambiguous_count: int
    review_needed_count: int
    optional_count: int


class GapSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class GapResult(BaseModel):
    """A concrete gap between a requirement and the dossier."""

    gap_id: str
    requirement_id: str
    dossier_section_id: Optional[str] = None
    description: str
    severity: GapSeverity
    recommendation: str
    review_status: ReviewStatus = ReviewStatus.not_started
    notes: Optional[str] = None


class GapList(BaseModel):
    items: List[GapResult]
    total: int


class ReadinessAssessmentRead(BaseModel):
    """Full readiness assessment result returned from the API."""

    id: int
    project_id: int
    job_id: int
    overall_score: float = Field(ge=0.0, le=1.0)
    summary: str
    module_scores: List[ModuleScore] = []
    gaps: List[GapResult] = []
    requirement_mappings: List[RequirementMapping] = []
    review_status: ReviewStatus = ReviewStatus.not_started
    algorithm_version: str = "0.1.0"
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Legacy aliases — kept so existing router code compiles unchanged
# ---------------------------------------------------------------------------

# GapRead is now GapResult; alias for back-compat during transition
GapRead = GapResult

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
