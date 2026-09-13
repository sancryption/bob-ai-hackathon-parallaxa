"""Weighted readiness scoring.

Module score formula (spec requirement 8)
-----------------------------------------
Only applicable mandatory requirements count in the denominator.
"Applicable" means requiredness == "mandatory" AND status != not_applicable.

    numerator   = sum(weight * score_value)  for applicable mandatory requirements
    denominator = sum(weight)                for applicable mandatory requirements

    score_value per status:
        complete                → 1.0
        present_needs_review    → 0.5   (credit for presence, penalty for review)
        missing                 → 0.0
        not_applicable          → excluded from denominator
        optional_not_submitted  → excluded from denominator

Overall score (spec requirement 9)
-----------------------------------
    overall = mean(module_score) over all modules with at least one
              applicable mandatory requirement.
    If no module has applicable mandatory requirements, overall = 0.0.

Score values are clamped to [0.0, 1.0].

Disclaimer: scores do NOT establish regulatory compliance.
"""
from __future__ import annotations

from typing import Dict, List

from app.services.readiness.types import (
    MappingResult,
    ModuleScoreResult,
    RequirementRecord,
    SectionReadinessStatus,
)

# Credit granted per status in the numerator
_STATUS_CREDIT: Dict[SectionReadinessStatus, float] = {
    SectionReadinessStatus.complete: 1.0,
    SectionReadinessStatus.present_needs_review: 0.5,
    SectionReadinessStatus.missing: 0.0,
    SectionReadinessStatus.not_applicable: 0.0,           # excluded from denominator too
    SectionReadinessStatus.optional_not_submitted: 0.0,   # excluded from denominator too
}

# Statuses that are excluded from the mandatory scoring denominator
_EXCLUDED_FROM_DENOMINATOR = {
    SectionReadinessStatus.not_applicable,
    SectionReadinessStatus.optional_not_submitted,
}


def score_module(
    module: str,
    requirements: List[RequirementRecord],
    mappings: List[MappingResult],
    catalog_version: str,
) -> ModuleScoreResult:
    """Compute the weighted readiness score for one CTD module.

    Parameters
    ----------
    module:
        CTD module number, e.g. "3".
    requirements:
        All RequirementRecord objects for this module.
    mappings:
        One MappingResult per requirement (same order).
    catalog_version:
        Stamped onto the result for provenance.
    """
    mapping_by_req: Dict[str, MappingResult] = {
        m.requirement_id: m for m in mappings
    }

    numerator = 0.0
    denominator = 0.0
    complete_count = 0
    present_needs_review_count = 0
    missing_count = 0
    not_applicable_count = 0
    optional_not_submitted_count = 0

    for req in requirements:
        mapping = mapping_by_req.get(req.requirement_id)
        if mapping is None:
            # Treat unmapped requirement as missing (conservative)
            status = SectionReadinessStatus.missing
        else:
            status = mapping.status

        # Count by status
        if status == SectionReadinessStatus.complete:
            complete_count += 1
        elif status == SectionReadinessStatus.present_needs_review:
            present_needs_review_count += 1
        elif status == SectionReadinessStatus.missing:
            missing_count += 1
        elif status == SectionReadinessStatus.not_applicable:
            not_applicable_count += 1
        elif status == SectionReadinessStatus.optional_not_submitted:
            optional_not_submitted_count += 1

        # Only mandatory requirements enter the score calculation
        if req.requiredness != "mandatory":
            continue

        # Excluded statuses don't affect the denominator or numerator
        if status in _EXCLUDED_FROM_DENOMINATOR:
            continue

        credit = _STATUS_CREDIT.get(status, 0.0)
        numerator += req.weight * credit
        denominator += req.weight

    if denominator == 0.0:
        score = 0.0
    else:
        score = max(0.0, min(1.0, numerator / denominator))

    return ModuleScoreResult(
        module=module,
        score=round(score, 6),
        weighted_score=round(numerator / denominator if denominator > 0 else 0.0, 6),
        complete_count=complete_count,
        present_needs_review_count=present_needs_review_count,
        missing_count=missing_count,
        not_applicable_count=not_applicable_count,
        optional_not_submitted_count=optional_not_submitted_count,
        applicable_mandatory_count=int(round(denominator)),  # approx when weights vary
        catalog_version=catalog_version,
    )


def score_all_modules(
    requirements: List[RequirementRecord],
    mappings: List[MappingResult],
    catalog_version: str,
) -> List[ModuleScoreResult]:
    """Compute per-module scores for all modules represented in ``requirements``."""
    # Group requirements and mappings by module
    req_by_module: Dict[str, List[RequirementRecord]] = {}
    for req in requirements:
        req_by_module.setdefault(req.module, []).append(req)

    module_scores: List[ModuleScoreResult] = []
    for module in sorted(req_by_module.keys()):
        module_reqs = req_by_module[module]
        module_mappings = [
            m for m in mappings
            if any(r.requirement_id == m.requirement_id for r in module_reqs)
        ]
        module_scores.append(
            score_module(module, module_reqs, module_mappings, catalog_version)
        )

    return module_scores


def score_overall(module_scores: List[ModuleScoreResult]) -> float:
    """Compute the overall score as the equal-weight mean of module scores.

    Only modules with at least one applicable mandatory requirement
    (applicable_mandatory_count > 0) contribute to the average.
    Returns 0.0 when no modules qualify.
    """
    qualifying = [ms for ms in module_scores if ms.applicable_mandatory_count > 0]
    if not qualifying:
        return 0.0
    avg = sum(ms.score for ms in qualifying) / len(qualifying)
    return round(max(0.0, min(1.0, avg)), 6)
