"""PRR (Proportional Reporting Ratio) computation.

Definitions
-----------
For a (drug D, event E) pair, given a dataset of N cases:

    a = |cases reporting D ∩ E|           (Drug+Event)
    b = |cases reporting D, not E|         (Drug+Other-event)
    c = |cases not D, reporting E|         (Other-drug+Event)
    d = |cases not D, not E|               (Other-drug+Other-event)

PRR = [a / (a + b)] / [c / (c + d)]

A zero in (a+b) or (c+d) yields prr=None with status=zero_denominator.

Confidence intervals (Evans 2001):
    ln(PRR) ± 1.96 * sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))
    → exp(ln(PRR) ± 1.96 * se)

Thresholds and ranking
----------------------
Thresholds are configurable via PRRConfig.  Defaults are sensible prototypes:
    - min_pair_count (a ≥ 3)
    - min_drug_reports (a+b ≥ 5)
    - min_event_reports (a+c ≥ 3)
    - min_prr (PRR ≥ 2.0)
    - chi_square_threshold (optional, disabled by default)

Ranking order:
    1. threshold_passing pairs first (above ≥ at > below > zero_denominator)
    2. descending PRR
    3. descending pair count (a)
    4. descending seriousness count (if provided)

Disclaimer: statistical signals do not prove causality.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.services.signal.types import (
    ContingencyTable,
    SignalResult,
    SignalSeverityLevel,
    ThresholdStatus,
    EventClusterResult,
    ALGORITHM_VERSION,
    DISCLAIMER,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PRRConfig:
    """Configurable thresholds for PRR signal detection."""

    min_pair_count: int = 3          # a ≥ this
    min_drug_reports: int = 5        # (a + b) ≥ this
    min_event_reports: int = 3       # (a + c) ≥ this
    min_prr: float = 2.0             # PRR ≥ this to be "above"
    chi_square_threshold: Optional[float] = None  # disabled when None
    algorithm_version: str = ALGORITHM_VERSION

    # PRR thresholds that map to severity levels
    prr_critical: float = 8.0
    prr_high: float = 4.0
    prr_medium: float = 2.0
    # below min_prr → low


# ---------------------------------------------------------------------------
# Case-level aggregation
# ---------------------------------------------------------------------------


def aggregate_case_drug_events(
    records: list,
) -> Tuple[
    Dict[str, Set[str]],  # case_id → set of canonical drug names
    Dict[str, Set[str]],  # case_id → set of canonical event preferred terms
]:
    """Build per-case drug and event sets from CanonicalRecord objects.

    Each (case_id, drug_canonical) and (case_id, event_canonical) is counted
    at most once — case-level deduplication.

    Parameters
    ----------
    records:
        List of CanonicalRecord objects that already have drug_canonical and
        event_canonical attributes set (by the engine after normalisation).

    Returns
    -------
    case_drugs:  case_id → frozenset of canonical drug names
    case_events: case_id → frozenset of canonical event preferred terms
    """
    case_drugs: Dict[str, Set[str]] = {}
    case_events: Dict[str, Set[str]] = {}

    for rec in records:
        cid = rec.case_id
        drug = getattr(rec, "drug_canonical", None) or rec.drug_raw.strip().upper()
        event = getattr(rec, "event_canonical", None) or rec.event_raw.strip().title()

        case_drugs.setdefault(cid, set()).add(drug)
        case_events.setdefault(cid, set()).add(event)

    return case_drugs, case_events


# ---------------------------------------------------------------------------
# Contingency table builder
# ---------------------------------------------------------------------------


def build_contingency_tables(
    case_drugs: Dict[str, Set[str]],
    case_events: Dict[str, Set[str]],
    seriousness_cases: Optional[Set[str]] = None,
) -> List[ContingencyTable]:
    """Compute 2×2 tables for all (drug, event) pairs.

    Parameters
    ----------
    case_drugs:
        case_id → set of canonical drug names for that case.
    case_events:
        case_id → set of canonical event preferred terms for that case.
    seriousness_cases:
        Optional set of case_ids flagged as serious (used for ranking).

    Returns
    -------
    List of ContingencyTable (unsorted, no rank assigned yet).
    """
    all_case_ids = set(case_drugs.keys()) | set(case_events.keys())

    # Collect all distinct drugs and events
    all_drugs: Set[str] = set()
    for drugs in case_drugs.values():
        all_drugs.update(drugs)

    all_events: Set[str] = set()
    for events in case_events.values():
        all_events.update(events)

    # Total cases
    n = len(all_case_ids)

    tables: List[ContingencyTable] = []

    for drug in sorted(all_drugs):
        for event in sorted(all_events):
            a = b = c = d = 0
            for cid in all_case_ids:
                has_drug = drug in case_drugs.get(cid, set())
                has_event = event in case_events.get(cid, set())
                if has_drug and has_event:
                    a += 1
                elif has_drug and not has_event:
                    b += 1
                elif not has_drug and has_event:
                    c += 1
                else:
                    d += 1

            prr, lower_ci, upper_ci = _calc_prr(a, b, c, d)
            tables.append(
                ContingencyTable(
                    drug=drug,
                    event=event,
                    a=a, b=b, c=c, d=d,
                    prr=prr,
                    prr_lower_ci=lower_ci,
                    prr_upper_ci=upper_ci,
                    threshold_status=ThresholdStatus.below,  # filled later
                    severity=SignalSeverityLevel.low,        # filled later
                    rank=0,                                  # filled later
                    algorithm_version=ALGORITHM_VERSION,
                )
            )

    return tables


# ---------------------------------------------------------------------------
# PRR calculation
# ---------------------------------------------------------------------------


def _calc_prr(
    a: int, b: int, c: int, d: int
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (prr, lower_95ci, upper_95ci).

    Returns (None, None, None) when any denominator is zero.
    """
    denom1 = a + b  # total drug reports
    denom2 = c + d  # total other-drug reports
    if denom1 == 0 or denom2 == 0 or c == 0:
        return None, None, None

    rate_drug = a / denom1
    rate_other = c / denom2

    if rate_other == 0:
        return None, None, None

    prr = rate_drug / rate_other

    # 95% CI via Evans (2001) log-normal approximation
    # Requires a > 0 for the formula to work
    if a > 0 and c > 0 and denom1 > 0 and denom2 > 0:
        try:
            se = math.sqrt(
                1 / a - 1 / denom1 + 1 / c - 1 / denom2
            )
            ln_prr = math.log(prr)
            lower_ci = math.exp(ln_prr - 1.96 * se)
            upper_ci = math.exp(ln_prr + 1.96 * se)
        except (ValueError, ZeroDivisionError):
            lower_ci = upper_ci = None
    else:
        lower_ci = upper_ci = None

    return round(prr, 6), (round(lower_ci, 6) if lower_ci else None), (round(upper_ci, 6) if upper_ci else None)


# ---------------------------------------------------------------------------
# Chi-square (optional)
# ---------------------------------------------------------------------------


def _chi_square(a: int, b: int, c: int, d: int) -> Optional[float]:
    """Yates-corrected chi-square for the 2×2 table."""
    n = a + b + c + d
    if n == 0:
        return None
    expected_a = (a + b) * (a + c) / n
    if expected_a == 0:
        return None
    # Standard chi-square (no Yates correction to keep it simple)
    chi2 = n * (a * d - b * c) ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))
    return round(chi2, 4) if math.isfinite(chi2) else None


# ---------------------------------------------------------------------------
# Threshold evaluation
# ---------------------------------------------------------------------------


def apply_thresholds(
    tables: List[ContingencyTable],
    config: PRRConfig,
    seriousness_counts: Optional[Dict[Tuple[str, str], int]] = None,
) -> List[ContingencyTable]:
    """Apply threshold rules and assign severity, threshold_status, and rank.

    Parameters
    ----------
    tables:
        Output of build_contingency_tables() — unranked.
    config:
        Threshold configuration.
    seriousness_counts:
        Optional mapping (drug, event) → count of serious cases.  Used for
        tie-breaking in ranking.

    Returns
    -------
    Ranked list (rank 1 = most important signal).
    """
    sc = seriousness_counts or {}

    for t in tables:
        # Determine threshold status
        if t.prr is None:
            t.threshold_status = ThresholdStatus.zero_denominator
        elif (
            t.a >= config.min_pair_count
            and (t.a + t.b) >= config.min_drug_reports
            and (t.a + t.c) >= config.min_event_reports
            and t.prr >= config.min_prr
        ):
            t.threshold_status = (
                ThresholdStatus.above
                if t.prr > config.min_prr
                else ThresholdStatus.at
            )
        else:
            t.threshold_status = ThresholdStatus.below

        # Severity
        if t.prr is not None:
            if t.prr >= config.prr_critical:
                t.severity = SignalSeverityLevel.critical
            elif t.prr >= config.prr_high:
                t.severity = SignalSeverityLevel.high
            elif t.prr >= config.prr_medium:
                t.severity = SignalSeverityLevel.medium
            else:
                t.severity = SignalSeverityLevel.low
        else:
            t.severity = SignalSeverityLevel.low

    # --- Ranking ---
    # Status priority: above > at > below > zero_denominator
    _status_priority = {
        ThresholdStatus.above: 0,
        ThresholdStatus.at: 1,
        ThresholdStatus.below: 2,
        ThresholdStatus.zero_denominator: 3,
    }

    def sort_key(t: ContingencyTable):
        serious = sc.get((t.drug, t.event), 0)
        return (
            _status_priority[t.threshold_status],
            -(t.prr if t.prr is not None else 0.0),
            -t.a,
            -serious,
        )

    tables.sort(key=sort_key)
    for i, t in enumerate(tables):
        t.rank = i + 1

    return tables


# ---------------------------------------------------------------------------
# Signal result builder
# ---------------------------------------------------------------------------


def build_signal_results(
    tables: List[ContingencyTable],
    clusters: Optional[Dict[str, EventClusterResult]] = None,
    config: Optional[PRRConfig] = None,
) -> List[SignalResult]:
    """Convert ContingencyTable objects into SignalResult objects.

    Only tables with threshold_status in (above, at) are included.
    Tables with status=below or zero_denominator are excluded from results.
    """
    cfg = config or PRRConfig()
    clusters = clusters or {}
    results: List[SignalResult] = []

    for t in tables:
        if t.threshold_status not in (ThresholdStatus.above, ThresholdStatus.at):
            continue

        cluster = clusters.get(t.event)

        results.append(
            SignalResult(
                drug=t.drug,
                event=t.event,
                a=t.a, b=t.b, c=t.c, d=t.d,
                prr=t.prr,
                prr_lower_ci=t.prr_lower_ci,
                prr_upper_ci=t.prr_upper_ci,
                threshold_status=t.threshold_status,
                severity=t.severity,
                rank=t.rank,
                algorithm_version=cfg.algorithm_version,
                disclaimer=DISCLAIMER,
                event_cluster=cluster,
            )
        )

    return results
