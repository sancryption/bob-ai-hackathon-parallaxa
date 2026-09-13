"""Typed result dataclasses for the signal detection pipeline.

All objects here are pure Python (no SQLAlchemy / SQLModel).  They flow
through the pipeline and can be serialised to JSON for persistence or API
responses.

Disclaimer: statistical signals computed here do not constitute proof of
causality.  For investigational use only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

ALGORITHM_VERSION = "0.1.0"

DISCLAIMER = (
    "These results are generated from post-marketing spontaneous reports and "
    "do not constitute proof of causality. For investigational use only."
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ThresholdStatus(str, Enum):
    below = "below"
    at = "at"
    above = "above"
    zero_denominator = "zero_denominator"


class SignalSeverityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class NormMethod(str, Enum):
    exact_match = "exact_match"
    alias_lookup = "alias_lookup"
    fuzzy = "fuzzy"
    passthrough = "passthrough"


# ---------------------------------------------------------------------------
# Normalisation provenance
# ---------------------------------------------------------------------------


@dataclass
class NormResult:
    """Result of normalising one raw term."""

    raw_term: str
    canonical: str              # normalised canonical form
    preferred_term: str         # human-readable preferred term
    meddra_code: Optional[str]
    method: NormMethod
    confidence: float           # 0.0 – 1.0


# ---------------------------------------------------------------------------
# Event cluster
# ---------------------------------------------------------------------------


@dataclass
class EventClusterResult:
    """A set of raw aliases that all resolved to the same preferred term."""

    preferred_term: str
    meddra_code: Optional[str]
    raw_aliases: List[str]
    case_count: int
    norm_results: List[NormResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Contingency table
# ---------------------------------------------------------------------------


@dataclass
class ContingencyTable:
    """Explicit 2×2 contingency table for one (drug, event) pair.

    Definitions (case-level, each case counted once per drug and once per event):
        a = cases reporting drug D AND event E
        b = cases reporting drug D but NOT event E
        c = cases NOT reporting drug D but reporting event E
        d = cases reporting neither drug D nor event E

    PRR = [a / (a + b)] / [c / (c + d)]

    A zero denominator in either ratio yields prr=None with
    threshold_status=zero_denominator.
    """

    drug: str           # canonical drug name
    event: str          # preferred event term

    a: int              # Drug+Event
    b: int              # Drug+Other-event
    c: int              # Other-drug+Event
    d: int              # Other-drug+Other-event

    prr: Optional[float]
    prr_lower_ci: Optional[float]
    prr_upper_ci: Optional[float]
    threshold_status: ThresholdStatus
    severity: SignalSeverityLevel
    rank: int
    algorithm_version: str = ALGORITHM_VERSION


# ---------------------------------------------------------------------------
# Signal result
# ---------------------------------------------------------------------------


@dataclass
class SignalResult:
    """A detected signal: contingency table plus metadata."""

    drug: str
    event: str

    a: int
    b: int
    c: int
    d: int

    prr: Optional[float]
    prr_lower_ci: Optional[float]
    prr_upper_ci: Optional[float]

    threshold_status: ThresholdStatus
    severity: SignalSeverityLevel
    rank: int

    algorithm_version: str
    disclaimer: str

    # optional cluster details for the event term
    event_cluster: Optional[EventClusterResult] = None


# ---------------------------------------------------------------------------
# Processing quality metrics
# ---------------------------------------------------------------------------


@dataclass
class ProcessingMetrics:
    """Metrics collected during one pipeline run."""

    total_raw_rows: int
    exact_duplicate_rows_removed: int
    old_version_rows_removed: int
    rows_after_dedup: int
    rows_dropped_missing_required: int
    rows_used: int
    distinct_drugs: int
    distinct_events_raw: int
    distinct_events_canonical: int
    total_drug_event_pairs: int
    pairs_above_threshold: int
    algorithm_version: str = ALGORITHM_VERSION


# ---------------------------------------------------------------------------
# Full pipeline output
# ---------------------------------------------------------------------------


@dataclass
class PipelineOutput:
    """Complete output from one signal detection run."""

    signals: List[SignalResult]
    clusters: List[EventClusterResult]
    metrics: ProcessingMetrics
    disclaimer: str = DISCLAIMER
