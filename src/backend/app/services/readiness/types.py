"""Typed dataclasses for the Submission Readiness pipeline.

All objects are pure Python — no ORM, no SQLAlchemy dependency.
They flow through the pipeline and are serialised to JSON for persistence
or API responses.

Disclaimer
----------
Scores computed here are prototype estimates and do NOT establish regulatory
compliance.  Always consult current ICH, FDA, EMA, or other applicable
authority guidance before using these results in a real regulatory submission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

READINESS_ALGORITHM_VERSION = "0.1.0"

READINESS_DISCLAIMER = (
    "This submission readiness score is a prototype estimate generated from "
    "structured dossier metadata.  It does NOT establish regulatory compliance.  "
    "Always consult current ICH, FDA, EMA, or other applicable authority guidance "
    "before submitting a regulatory dossier."
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MappingMethod(str, Enum):
    exact_code = "exact_code"
    normalised_code = "normalised_code"
    keyword_title = "keyword_title"
    fuzzy_title = "fuzzy_title"
    unmatched = "unmatched"


class SectionReadinessStatus(str, Enum):
    """Granular completeness status for one requirement."""

    complete = "complete"
    present_needs_review = "present_needs_review"
    missing = "missing"
    not_applicable = "not_applicable"
    optional_not_submitted = "optional_not_submitted"


class GapSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Requirement record (richer than the ORM model – for in-memory use)
# ---------------------------------------------------------------------------


@dataclass
class RequirementRecord:
    """One CTD requirement as it flows through the readiness pipeline.

    Fields align with the requirement specification:
    requirement_id, module, section_code, title, expected_content,
    requiredness, applicability_rule, keywords, weight, catalog_version.
    """

    requirement_id: str            # e.g. "CTD-3.2.S.1"
    module: str                    # "1"–"5"
    section_code: str              # e.g. "3.2.S.1"
    title: str
    expected_content: str          # human-readable description of what is expected
    requiredness: str              # "mandatory" | "optional" | "conditional"
    applicability_rule: str        # e.g. "always" | "if_new_molecular_entity" | …
    keywords: List[str]            # title/content keywords for keyword mapping
    weight: float                  # scoring weight (default 1.0)
    catalog_version: str           # e.g. "0.1.0"
    guidance_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Dossier section record
# ---------------------------------------------------------------------------


@dataclass
class DossierSectionRecord:
    """One section extracted from a dossier outline.

    Preserves all fields required by the specification:
    section_id, module_hint, section_code, title, summary,
    content_present, source.
    """

    section_id: str                # e.g. "SEC-3.2.S.1" or "3.2.S.1"
    module_hint: str               # module number inferred from section_id / code
    section_code: str              # normalised code, e.g. "3.2.S.1"
    title: str
    summary: Optional[str]
    content_present: bool          # True unless status=missing or optional_not_submitted
    source: str                    # e.g. "json_outline" | "csv_outline" | "text"
    # Source status from dossier (complete/missing/ambiguous/optional/review_needed)
    raw_status: str = "unknown"
    page_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Mapping result
# ---------------------------------------------------------------------------


@dataclass
class MappingResult:
    """Result of mapping one RequirementRecord to zero or one dossier section."""

    requirement_id: str
    section_code: str              # from the requirement
    matched_section_id: Optional[str]  # DossierSectionRecord.section_id if matched
    mapping_method: MappingMethod
    confidence: float              # 0.0–1.0
    status: SectionReadinessStatus
    review_status: str             # "not_started" | "flagged" | "approved"
    # List of section_ids that contributed evidence (empty for missing/not_applicable)
    evidence: List[str]
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Module score
# ---------------------------------------------------------------------------


@dataclass
class ModuleScoreResult:
    """Weighted readiness score for one CTD module."""

    module: str
    score: float                   # 0.0–1.0
    weighted_score: float          # raw numerator / denominator before clamping
    complete_count: int
    present_needs_review_count: int
    missing_count: int
    not_applicable_count: int
    optional_not_submitted_count: int
    applicable_mandatory_count: int  # denominator (excludes optional + not_applicable)
    catalog_version: str


# ---------------------------------------------------------------------------
# Gap record
# ---------------------------------------------------------------------------


@dataclass
class GapRecord:
    """A concrete gap with deterministic description and recommendation."""

    gap_id: str
    requirement_id: str
    section_code: str
    title: str
    severity: GapSeverity
    status: SectionReadinessStatus
    description: str               # generated deterministically from metadata
    recommendation: str            # generated deterministically from metadata
    matched_section_id: Optional[str]
    evidence: List[str]


# ---------------------------------------------------------------------------
# Full assessment output
# ---------------------------------------------------------------------------


@dataclass
class ReadinessOutput:
    """Complete output from one readiness assessment run."""

    overall_score: float
    summary: str
    module_scores: List[ModuleScoreResult]
    mappings: List[MappingResult]
    gaps: List[GapRecord]
    algorithm_version: str = READINESS_ALGORITHM_VERSION
    catalog_version: str = "0.1.0"
    disclaimer: str = READINESS_DISCLAIMER
