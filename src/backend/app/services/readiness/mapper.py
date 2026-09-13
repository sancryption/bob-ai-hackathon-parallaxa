"""Section mapper: deterministic 4-tier mapping of dossier sections to CTD requirements.

Mapping priority order (spec requirement 5)
-------------------------------------------
1. Exact section code          – section_code from dossier == section_code from catalog
2. Normalised code             – both codes normalised (lower, strip dots/spaces) match
3. Controlled keyword/title    – title or summary contain one or more catalog keywords
4. High-threshold fuzzy title  – rapidfuzz token_set_ratio ≥ 0.85

Outputs (spec requirements 6 & 7)
----------------------------------
Each RequirementRecord → MappingResult with:
  - mapping_method (exact_code | normalised_code | keyword_title | fuzzy_title | unmatched)
  - confidence (0.0–1.0)
  - matched_section_id (or None)
  - status (complete | present_needs_review | missing | not_applicable | optional_not_submitted)
  - review_status ("not_started" | "flagged")
  - evidence list

Status assignment rules
-----------------------
If a matched section exists its raw_status drives the readiness status:
  complete         → SectionReadinessStatus.complete            (confidence 1.0)
  review_needed    → SectionReadinessStatus.present_needs_review
  ambiguous        → SectionReadinessStatus.present_needs_review (review flagged)
  optional         → SectionReadinessStatus.optional_not_submitted
  missing          → SectionReadinessStatus.missing

If no section is matched:
  mandatory/conditional requirement → SectionReadinessStatus.missing
  optional requirement              → SectionReadinessStatus.optional_not_submitted

Applicability
-------------
If the requirement has applicability_rule != "always" and no section matches,
the status may be SectionReadinessStatus.not_applicable when the caller
supplies a context dict that signals the rule does not apply.
For the MVP the engine never infers not_applicable automatically unless
a section with status="optional" is explicitly submitted – that case is
optional_not_submitted.  not_applicable must be set by the caller via
override_status.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from rapidfuzz import fuzz, process as rp

from app.services.readiness.types import (
    DossierSectionRecord,
    MappingMethod,
    MappingResult,
    RequirementRecord,
    SectionReadinessStatus,
)

# High-confidence fuzzy threshold (0–100 scale internally)
_FUZZY_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Code normalisation
# ---------------------------------------------------------------------------

_NORM_RE = re.compile(r"[\s\.\-]")


def _norm_code(code: str) -> str:
    """Normalise a section code: lower, strip dots/spaces/dashes."""
    return _NORM_RE.sub("", code.lower().strip())


# ---------------------------------------------------------------------------
# Status mapping from raw dossier status
# ---------------------------------------------------------------------------


def _raw_status_to_readiness(
    raw_status: str,
    requiredness: str,
) -> tuple[SectionReadinessStatus, str, float]:
    """Map a raw dossier status to a SectionReadinessStatus.

    Returns (status, review_status, confidence).
    """
    rs = raw_status.strip().lower()
    if rs == "complete":
        return SectionReadinessStatus.complete, "not_started", 1.0
    if rs == "review_needed":
        return SectionReadinessStatus.present_needs_review, "flagged", 0.8
    if rs == "ambiguous":
        return SectionReadinessStatus.present_needs_review, "flagged", 0.6
    if rs in ("optional", "optional_not_submitted"):
        return SectionReadinessStatus.optional_not_submitted, "not_started", 1.0
    if rs == "missing":
        return SectionReadinessStatus.missing, "not_started", 1.0
    # Unknown / fallback
    return SectionReadinessStatus.present_needs_review, "flagged", 0.5


# ---------------------------------------------------------------------------
# Main mapper
# ---------------------------------------------------------------------------


def map_requirements(
    requirements: List[RequirementRecord],
    sections: List[DossierSectionRecord],
    override_status: Optional[Dict[str, SectionReadinessStatus]] = None,
) -> List[MappingResult]:
    """Map each requirement to the best matching dossier section.

    Parameters
    ----------
    requirements:
        Full list of RequirementRecord objects from the catalog.
    sections:
        Parsed DossierSectionRecord objects from the dossier outline.
    override_status:
        Optional dict {requirement_id: SectionReadinessStatus} to force a
        status for specific requirements (e.g. not_applicable).

    Returns
    -------
    One MappingResult per requirement (same order as ``requirements``).
    """
    overrides = override_status or {}

    # Build indices for fast look-up
    by_exact_code: Dict[str, DossierSectionRecord] = {
        s.section_code: s for s in sections if s.section_code
    }
    by_norm_code: Dict[str, DossierSectionRecord] = {}
    for s in sections:
        nc = _norm_code(s.section_code)
        if nc:
            by_norm_code.setdefault(nc, s)

    # Pre-build title list for fuzzy matching
    section_titles = [s.title for s in sections]

    results: List[MappingResult] = []

    for req in requirements:
        # --- Override ---
        if req.requirement_id in overrides:
            forced = overrides[req.requirement_id]
            results.append(
                MappingResult(
                    requirement_id=req.requirement_id,
                    section_code=req.section_code,
                    matched_section_id=None,
                    mapping_method=MappingMethod.unmatched,
                    confidence=1.0,
                    status=forced,
                    review_status="not_started",
                    evidence=[],
                    notes="status set by caller override",
                )
            )
            continue

        # --- Tier 1: Exact section code ---
        matched: Optional[DossierSectionRecord] = by_exact_code.get(req.section_code)
        method = MappingMethod.exact_code
        tier_confidence = 1.0

        # --- Tier 2: Normalised code ---
        if matched is None:
            norm_req = _norm_code(req.section_code)
            matched = by_norm_code.get(norm_req)
            method = MappingMethod.normalised_code
            tier_confidence = 0.95

        # --- Tier 3: Keyword / title match ---
        if matched is None:
            matched = _keyword_match(req, sections)
            method = MappingMethod.keyword_title
            tier_confidence = 0.80

        # --- Tier 4: Fuzzy title match ---
        if matched is None and section_titles:
            matched, fuzzy_score = _fuzzy_match(req, sections, section_titles)
            method = MappingMethod.fuzzy_title
            tier_confidence = round(fuzzy_score / 100.0, 4) if fuzzy_score is not None else 0.0

        # --- Status resolution ---
        if matched is not None:
            status, rev, raw_conf = _raw_status_to_readiness(
                matched.raw_status, req.requiredness
            )
            # Use the lower of tier confidence and raw confidence for fuzzy/keyword
            if method in (MappingMethod.keyword_title, MappingMethod.fuzzy_title):
                confidence = round(min(tier_confidence, raw_conf), 4)
            else:
                confidence = raw_conf
            evidence = [matched.section_id]
        else:
            # No match found
            method = MappingMethod.unmatched
            confidence = 0.0
            evidence = []
            rev = "not_started"
            if req.requiredness == "optional":
                status = SectionReadinessStatus.optional_not_submitted
            else:
                status = SectionReadinessStatus.missing

        results.append(
            MappingResult(
                requirement_id=req.requirement_id,
                section_code=req.section_code,
                matched_section_id=matched.section_id if matched else None,
                mapping_method=method,
                confidence=confidence,
                status=status,
                review_status=rev,
                evidence=evidence,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Tier-3: keyword/title match
# ---------------------------------------------------------------------------


# Minimum number of keyword hits required to accept a keyword match.
# A single-word hit is too loose (e.g. "summary" matches almost everything).
_KEYWORD_MIN_HITS = 2


def _keyword_match(
    req: RequirementRecord,
    sections: List[DossierSectionRecord],
) -> Optional[DossierSectionRecord]:
    """Find the best section that contains at least _KEYWORD_MIN_HITS catalog keywords.

    Longer keywords (≥ 8 chars) count as a "strong" hit; a single strong hit
    also qualifies, so we don't miss unambiguous long phrases.
    """
    keywords_lower = [k.lower() for k in req.keywords]

    best: Optional[DossierSectionRecord] = None
    best_hits = 0

    for sec in sections:
        target = ((sec.title or "") + " " + (sec.summary or "")).lower()
        hits = sum(1 for kw in keywords_lower if kw in target)
        strong_hits = sum(1 for kw in keywords_lower if len(kw) >= 8 and kw in target)
        # Accept if: 2+ total hits OR 1+ strong (long, specific) hit
        if hits >= _KEYWORD_MIN_HITS or strong_hits >= 1:
            if hits > best_hits:
                best_hits = hits
                best = sec

    return best


# ---------------------------------------------------------------------------
# Tier-4: fuzzy title match
# ---------------------------------------------------------------------------


def _fuzzy_match(
    req: RequirementRecord,
    sections: List[DossierSectionRecord],
    section_titles: List[str],
) -> tuple[Optional[DossierSectionRecord], Optional[float]]:
    """Return the best-scoring section above the fuzzy threshold."""
    result = rp.extractOne(
        req.title,
        section_titles,
        scorer=fuzz.token_set_ratio,
        score_cutoff=_FUZZY_THRESHOLD,
    )
    if result is None:
        return None, None
    _match_title, score, idx = result
    return sections[idx], float(score)
