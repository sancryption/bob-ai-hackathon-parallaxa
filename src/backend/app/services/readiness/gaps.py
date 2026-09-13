"""Deterministic gap report generator.

For each MappingResult that is NOT complete or optional_not_submitted, a
GapRecord is produced with:
  - a machine-generated gap_id  (GAP-<module>-<zero-padded-sequence>)
  - severity derived from status + requiredness
  - a deterministic description built from requirement metadata
  - a deterministic recommendation built from requirement metadata

No LLM is used.  All text is assembled from template strings and
requirement fields (title, expected_content, guidance_ref).

Severity rules
--------------
    missing         + mandatory     → high
    missing         + conditional   → high
    present_needs_review + mandatory → medium
    present_needs_review + conditional → medium
    missing         + optional      → low (edge case — should be optional_not_submitted)
    present_needs_review + optional  → low

The gap generator does NOT produce gaps for:
  - complete
  - not_applicable
  - optional_not_submitted
"""
from __future__ import annotations

from typing import Dict, List

from app.services.readiness.types import (
    GapRecord,
    GapSeverity,
    MappingResult,
    RequirementRecord,
    SectionReadinessStatus,
)


def _severity(
    status: SectionReadinessStatus,
    requiredness: str,
) -> GapSeverity:
    """Determine gap severity from status and requiredness."""
    if status == SectionReadinessStatus.missing:
        if requiredness in ("mandatory", "conditional"):
            return GapSeverity.high
        return GapSeverity.low
    if status == SectionReadinessStatus.present_needs_review:
        if requiredness in ("mandatory", "conditional"):
            return GapSeverity.medium
        return GapSeverity.low
    return GapSeverity.low


def _description(
    req: RequirementRecord,
    status: SectionReadinessStatus,
    matched_section_id: str | None,
) -> str:
    """Generate a deterministic description from requirement metadata."""
    if status == SectionReadinessStatus.missing:
        return (
            f"Section '{req.title}' ({req.section_code}) is required by the CTD "
            f"catalog (requirement {req.requirement_id}) but was not found in the "
            f"submitted dossier.  Expected content: {req.expected_content}"
        )
    if status == SectionReadinessStatus.present_needs_review:
        section_ref = f"'{matched_section_id}'" if matched_section_id else "an unverified section"
        return (
            f"Section '{req.title}' ({req.section_code}) was found at "
            f"{section_ref} but requires further review before it can be "
            f"considered complete.  Expected content: {req.expected_content}"
        )
    return (
        f"Section '{req.title}' ({req.section_code}) requires attention "
        f"(status: {status.value}).  Expected content: {req.expected_content}"
    )


def _recommendation(
    req: RequirementRecord,
    status: SectionReadinessStatus,
) -> str:
    """Generate a deterministic recommendation from requirement metadata."""
    guidance = f"  Reference: {req.guidance_ref}." if req.guidance_ref else ""
    if status == SectionReadinessStatus.missing:
        return (
            f"Prepare and include section {req.section_code} — '{req.title}' — "
            f"in the submission dossier.  Ensure it covers: {req.expected_content}"
            f"{guidance}"
        )
    if status == SectionReadinessStatus.present_needs_review:
        return (
            f"Review and complete section {req.section_code} — '{req.title}'.  "
            f"Verify that all required content is present: {req.expected_content}"
            f"{guidance}"
        )
    return (
        f"Address the identified issue in section {req.section_code} — "
        f"'{req.title}'.{guidance}"
    )


# Statuses that produce a gap
_GAP_STATUSES = {
    SectionReadinessStatus.missing,
    SectionReadinessStatus.present_needs_review,
}


def generate_gaps(
    requirements: List[RequirementRecord],
    mappings: List[MappingResult],
) -> List[GapRecord]:
    """Generate GapRecord objects for all non-complete, non-exempt mappings.

    Parameters
    ----------
    requirements:
        Full list of RequirementRecord objects (order determines gap_id sequence).
    mappings:
        One MappingResult per requirement.

    Returns
    -------
    List of GapRecord, ordered module-major, then by severity (high → medium → low),
    then by requirement_id.
    """
    req_by_id: Dict[str, RequirementRecord] = {r.requirement_id: r for r in requirements}
    gaps: List[GapRecord] = []
    seq = 1

    # Sort by module then requirement_id for deterministic gap_id assignment
    sorted_mappings = sorted(
        mappings,
        key=lambda m: (
            req_by_id[m.requirement_id].module
            if m.requirement_id in req_by_id else "9",
            m.requirement_id,
        ),
    )

    for mapping in sorted_mappings:
        if mapping.status not in _GAP_STATUSES:
            continue

        req = req_by_id.get(mapping.requirement_id)
        if req is None:
            continue

        sev = _severity(mapping.status, req.requiredness)

        gaps.append(
            GapRecord(
                gap_id=f"GAP-{req.module}-{seq:03d}",
                requirement_id=req.requirement_id,
                section_code=req.section_code,
                title=req.title,
                severity=sev,
                status=mapping.status,
                description=_description(req, mapping.status, mapping.matched_section_id),
                recommendation=_recommendation(req, mapping.status),
                matched_section_id=mapping.matched_section_id,
                evidence=mapping.evidence,
            )
        )
        seq += 1

    return gaps
