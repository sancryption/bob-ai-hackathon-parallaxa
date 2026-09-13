"""Model package — importing all ORM classes here registers them with
SQLModel.metadata so that create_all() and drop_all() see every table.
"""
# Shared / infrastructure
from app.models.project import Project, ProjectStatus  # noqa: F401
from app.models.shared import (  # noqa: F401
    Upload,
    UploadStatus,
    Job,
    JobType,
    JobStatus,
    AuditEvent,
)

# Signal detection domain
from app.models.signal import (  # noqa: F401
    Report,
    Drug,
    AdverseEvent,
    ReportDrug,
    ReportEvent,
    DrugEventPair,
    Signal,
    SignalSeverity,
)

# Readiness assessment domain
from app.models.readiness import (  # noqa: F401
    CtdRequirement,
    DossierSection,
    ReadinessAssessment,
    RequirementMapping,
    Gap,
    SectionStatus,
    ReviewStatus,
    GapSeverity,
)

__all__ = [
    # project
    "Project",
    "ProjectStatus",
    # shared
    "Upload",
    "UploadStatus",
    "Job",
    "JobType",
    "JobStatus",
    "AuditEvent",
    # signal
    "Report",
    "Drug",
    "AdverseEvent",
    "ReportDrug",
    "ReportEvent",
    "DrugEventPair",
    "Signal",
    "SignalSeverity",
    # readiness
    "CtdRequirement",
    "DossierSection",
    "ReadinessAssessment",
    "RequirementMapping",
    "Gap",
    "SectionStatus",
    "ReviewStatus",
    "GapSeverity",
]
