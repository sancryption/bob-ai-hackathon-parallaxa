"""Drug and adverse-event normalisation.

Architecture
------------
1. Checked-in alias dictionary (DRUG_ALIASES, EVENT_ALIASES) is consulted
   first — exact, case-insensitive look-up → confidence 1.0.
2. Canonical name look-up (normalised upper-case) → confidence 1.0,
   method=exact_match.
3. rapidfuzz token_set_ratio for high-confidence fuzzy matching (≥ 0.90)
   among known canonical terms → method=fuzzy.
4. Passthrough: raw term stripped and title-cased, confidence 0.5.

Clustering
----------
Event terms that resolve to the same preferred_term form a cluster.
The cluster is built deterministically from the alias dictionary first;
aliases that fall through to fuzzy are added to the cluster if their
canonical resolves to an existing preferred term.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from rapidfuzz import process as rp, fuzz

from app.services.signal.types import NormMethod, NormResult


# ---------------------------------------------------------------------------
# Drug alias dictionary
# Keyed on lower-stripped alias → canonical UPPER name.
# ---------------------------------------------------------------------------

DRUG_ALIASES: Dict[str, str] = {
    # Add project-specific aliases here to extend without code changes.
    # Format: "raw alias lower" : "CANONICAL_NAME"
}


# ---------------------------------------------------------------------------
# Event alias dictionary
# Keyed on lower-stripped alias → (preferred_term, meddra_code)
# ---------------------------------------------------------------------------

# Each entry:  alias_lower : (preferred_term, meddra_code or None)
EVENT_ALIASES: Dict[str, Tuple[str, Optional[str]]] = {
    # Headache cluster
    "headache":           ("Headache", "10019211"),
    "severe headache":    ("Headache", "10019211"),
    "head ache":          ("Headache", "10019211"),
    "migraine":           ("Headache", "10019211"),

    # Hepatic disorder cluster
    "liver injury":       ("Hepatic disorder", "10019692"),
    "hepatic failure":    ("Hepatic disorder", "10019692"),
    "liver failure":      ("Hepatic disorder", "10019692"),
    "hepatic disorder":   ("Hepatic disorder", "10019692"),
    "hepatic damage":     ("Hepatic disorder", "10019692"),
    "liver damage":       ("Hepatic disorder", "10019692"),
    "jaundice":           ("Hepatic disorder", "10019692"),

    # Nausea (no grouping with vomiting by default — distinct preferred terms)
    "nausea":             ("Nausea", "10028813"),
    "nauseated":          ("Nausea", "10028813"),

    # Vomiting
    "vomiting":           ("Vomiting", "10047700"),
    "vomited":            ("Vomiting", "10047700"),
    "emesis":             ("Vomiting", "10047700"),

    # Rash
    "rash":               ("Rash", "10037844"),
    "skin rash":          ("Rash", "10037844"),
    "erythema":           ("Rash", "10015150"),

    # Fatigue
    "fatigue":            ("Fatigue", "10016256"),
    "tiredness":          ("Fatigue", "10016256"),
    "asthenia":           ("Fatigue", "10003549"),
}

# Build a reverse map: preferred_term → meddra_code
_PREFERRED_TO_MEDDRA: Dict[str, Optional[str]] = {}
for _alias, (_pt, _code) in EVENT_ALIASES.items():
    if _pt not in _PREFERRED_TO_MEDDRA:
        _PREFERRED_TO_MEDDRA[_pt] = _code

# All known canonical preferred terms for fuzzy matching
_ALL_PREFERRED_TERMS: List[str] = list(_PREFERRED_TO_MEDDRA.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[^a-z0-9 ]")


def _normalise_key(raw: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    return _STRIP_RE.sub("", raw.lower()).strip()


# ---------------------------------------------------------------------------
# Drug normalisation
# ---------------------------------------------------------------------------


def normalise_drug(raw: str) -> NormResult:
    """Normalise a raw drug name.

    Strategy:
    1. Exact alias look-up (case-insensitive stripped).
    2. Upper-case as canonical (passthrough).
    """
    key = _normalise_key(raw)
    canonical_upper = raw.strip().upper()

    if key in DRUG_ALIASES:
        canonical = DRUG_ALIASES[key]
        return NormResult(
            raw_term=raw,
            canonical=canonical,
            preferred_term=canonical,
            meddra_code=None,
            method=NormMethod.alias_lookup,
            confidence=1.0,
        )

    # Simple passthrough — drugs are reported by proper name
    return NormResult(
        raw_term=raw,
        canonical=canonical_upper,
        preferred_term=canonical_upper,
        meddra_code=None,
        method=NormMethod.exact_match,
        confidence=1.0,
    )


# ---------------------------------------------------------------------------
# Event normalisation
# ---------------------------------------------------------------------------

# Fuzzy confidence threshold — only accept matches at or above this score.
_FUZZY_THRESHOLD = 0.90


def normalise_event(raw: str) -> NormResult:
    """Normalise a raw adverse-event term.

    1. Exact alias dictionary look-up.
    2. High-confidence rapidfuzz match against known preferred terms (≥ 0.90).
    3. Passthrough: title-cased raw, confidence 0.5.
    """
    key = _normalise_key(raw)

    # Step 1: exact alias
    if key in EVENT_ALIASES:
        pt, code = EVENT_ALIASES[key]
        return NormResult(
            raw_term=raw,
            canonical=pt,
            preferred_term=pt,
            meddra_code=code,
            method=NormMethod.alias_lookup,
            confidence=1.0,
        )

    # Step 2: fuzzy match against known preferred terms
    if _ALL_PREFERRED_TERMS:
        best = rp.extractOne(
            raw,
            _ALL_PREFERRED_TERMS,
            scorer=fuzz.token_set_ratio,
            score_cutoff=_FUZZY_THRESHOLD * 100,
        )
        if best is not None:
            match_term, score, _ = best
            confidence = round(score / 100.0, 4)
            code = _PREFERRED_TO_MEDDRA.get(match_term)
            return NormResult(
                raw_term=raw,
                canonical=match_term,
                preferred_term=match_term,
                meddra_code=code,
                method=NormMethod.fuzzy,
                confidence=confidence,
            )

    # Step 3: passthrough
    pt = raw.strip().title()
    return NormResult(
        raw_term=raw,
        canonical=pt,
        preferred_term=pt,
        meddra_code=None,
        method=NormMethod.passthrough,
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# Cluster builder
# ---------------------------------------------------------------------------


def build_event_clusters(
    raw_terms: List[str],
    case_counts: Dict[str, int],
) -> Dict[str, "EventClusterInfo"]:
    """Group raw terms into clusters by preferred_term.

    Parameters
    ----------
    raw_terms:
        All distinct raw event terms observed in the dataset.
    case_counts:
        Mapping raw_term → number of distinct cases mentioning it.

    Returns
    -------
    Dict mapping preferred_term → EventClusterInfo.
    """
    from app.services.signal.types import EventClusterResult

    clusters: Dict[str, EventClusterResult] = {}
    norm_cache: Dict[str, NormResult] = {}

    for raw in raw_terms:
        nr = normalise_event(raw)
        norm_cache[raw] = nr
        pt = nr.preferred_term
        if pt not in clusters:
            clusters[pt] = EventClusterResult(
                preferred_term=pt,
                meddra_code=nr.meddra_code,
                raw_aliases=[],
                case_count=0,
                norm_results=[],
            )
        clusters[pt].raw_aliases.append(raw)
        clusters[pt].case_count += case_counts.get(raw, 0)
        clusters[pt].norm_results.append(nr)

    return clusters
