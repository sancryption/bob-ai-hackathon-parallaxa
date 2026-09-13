"""SignalEngine — orchestrates the complete signal detection pipeline.

Pipeline
--------
ingest() → normalise() → cluster_events() → aggregate() →
build_contingency_tables() → apply_thresholds() → build_signal_results()
→ (optional) persist to database

Usage (pure / no DB)
--------------------
    from app.services.signal.engine import SignalEngine, SignalEngineConfig

    engine = SignalEngineConfig()
    result = SignalEngine(config).run_from_csv(csv_text)

Usage (with DB persistence)
---------------------------
    from sqlmodel import Session
    result = SignalEngine(config).run_and_persist(csv_text, session, project_id, job_id, upload_id)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from app.services.signal.ingestion import (
    CanonicalRecord,
    IngestionResult,
    IngestionMetrics,
    ingest,
    _build_column_map,
)
from app.services.signal.normalisation import (
    normalise_drug,
    normalise_event,
    build_event_clusters,
)
from app.services.signal.prr import (
    PRRConfig,
    aggregate_case_drug_events,
    build_contingency_tables,
    apply_thresholds,
    build_signal_results,
)
from app.services.signal.types import (
    EventClusterResult,
    PipelineOutput,
    ProcessingMetrics,
    SignalResult,
    ALGORITHM_VERSION,
    DISCLAIMER,
)


# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------


@dataclass
class SignalEngineConfig:
    """Top-level configuration for one engine run."""

    prr: PRRConfig = field(default_factory=PRRConfig)
    algorithm_version: str = ALGORITHM_VERSION
    # Fuzzy confidence gate — events normalised with confidence < this value
    # are flagged but still processed.
    min_norm_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Enriched canonical record (internal, after normalisation)
# ---------------------------------------------------------------------------


@dataclass
class _EnrichedRecord:
    """CanonicalRecord extended with normalised drug and event fields."""

    # delegate to the underlying record
    case_id: str
    drug_raw: str
    event_raw: str
    primaryid: Optional[str]
    case_version: str
    receipt_date: Optional[str]
    drug_role: Optional[str]
    seriousness: Optional[str]
    outcome: Optional[str]
    age_group: Optional[str]
    sex: Optional[str]
    reporter_country: Optional[str]
    source_row: Optional[int]

    # Normalised fields
    drug_canonical: str = ""
    event_canonical: str = ""


def _enrich(rec: CanonicalRecord) -> _EnrichedRecord:
    drug_nr = normalise_drug(rec.drug_raw)
    event_nr = normalise_event(rec.event_raw)
    return _EnrichedRecord(
        case_id=rec.case_id,
        drug_raw=rec.drug_raw,
        event_raw=rec.event_raw,
        primaryid=rec.primaryid,
        case_version=rec.case_version,
        receipt_date=rec.receipt_date,
        drug_role=rec.drug_role,
        seriousness=rec.seriousness,
        outcome=rec.outcome,
        age_group=rec.age_group,
        sex=rec.sex,
        reporter_country=rec.reporter_country,
        source_row=rec.source_row,
        drug_canonical=drug_nr.canonical,
        event_canonical=event_nr.preferred_term,
    )


# ---------------------------------------------------------------------------
# SignalEngine
# ---------------------------------------------------------------------------


class SignalEngine:
    """Deterministic signal detection engine.

    All computations are pure and reproducible given the same input.
    """

    def __init__(self, config: Optional[SignalEngineConfig] = None) -> None:
        self._config = config or SignalEngineConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_from_csv(self, csv_text: str) -> PipelineOutput:
        """Run the full pipeline on raw CSV text.  No DB interaction."""
        ingestion = ingest(csv_text, fmt="csv")
        return self._run_pipeline(ingestion)

    def run_from_json(self, json_text: str) -> PipelineOutput:
        """Run the full pipeline on a JSON string (list or {records:[…]})."""
        ingestion = ingest(json_text, fmt="json")
        return self._run_pipeline(ingestion)

    def run_and_persist(
        self,
        csv_text: str,
        session,
        project_id: int,
        job_id: int,
        upload_id: int,
    ) -> PipelineOutput:
        """Run the pipeline and persist results to the database."""
        output = self.run_from_csv(csv_text)
        self._persist(output, session, project_id, job_id, upload_id)
        return output

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(self, ingestion: IngestionResult) -> PipelineOutput:
        records = ingestion.records
        ing_metrics = ingestion.metrics

        # --- Normalise each record ---
        enriched: List[_EnrichedRecord] = [_enrich(r) for r in records]

        # --- Build per-raw-term event case counts (for clustering) ---
        raw_event_case_counts: Dict[str, set] = {}
        for rec in enriched:
            raw_event_case_counts.setdefault(rec.event_raw, set()).add(rec.case_id)
        raw_event_counts_int: Dict[str, int] = {
            k: len(v) for k, v in raw_event_case_counts.items()
        }

        clusters: Dict[str, EventClusterResult] = build_event_clusters(
            list(raw_event_case_counts.keys()),
            raw_event_counts_int,
        )

        # --- Case-level drug/event deduplication + aggregation ---
        case_drugs, case_events = aggregate_case_drug_events(enriched)

        # --- Seriousness counts per (drug, event) pair ---
        serious_counts: Dict[tuple, int] = {}
        for rec in enriched:
            if str(rec.seriousness or "").strip().upper() in ("Y", "1", "YES", "SERIOUS"):
                key = (rec.drug_canonical, rec.event_canonical)
                serious_counts[key] = serious_counts.get(key, 0) + 1

        # --- Contingency tables ---
        tables = build_contingency_tables(case_drugs, case_events)

        # --- Thresholds + ranking ---
        tables = apply_thresholds(
            tables,
            self._config.prr,
            seriousness_counts=serious_counts,
        )

        # --- Signal results (above/at threshold only) ---
        signal_results = build_signal_results(
            tables,
            clusters=clusters,
            config=self._config.prr,
        )

        # --- Processing quality metrics ---
        distinct_drugs = len({rec.drug_canonical for rec in enriched})
        distinct_events_raw = len(raw_event_case_counts)
        distinct_events_canonical = len(clusters)
        pairs_above = sum(
            1 for r in signal_results
            if r.threshold_status.value in ("above", "at")
        )

        metrics = ProcessingMetrics(
            total_raw_rows=ing_metrics.total_raw_rows,
            exact_duplicate_rows_removed=ing_metrics.exact_duplicate_rows_removed,
            old_version_rows_removed=ing_metrics.old_version_rows_removed,
            rows_after_dedup=ing_metrics.rows_after_dedup,
            rows_dropped_missing_required=ing_metrics.rows_dropped_missing_required,
            rows_used=ing_metrics.rows_used,
            distinct_drugs=distinct_drugs,
            distinct_events_raw=distinct_events_raw,
            distinct_events_canonical=distinct_events_canonical,
            total_drug_event_pairs=len(tables),
            pairs_above_threshold=pairs_above,
            algorithm_version=self._config.algorithm_version,
        )

        return PipelineOutput(
            signals=signal_results,
            clusters=list(clusters.values()),
            metrics=metrics,
            disclaimer=DISCLAIMER,
        )

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _persist(
        self,
        output: PipelineOutput,
        session,
        project_id: int,
        job_id: int,
        upload_id: int,
    ) -> None:
        """Persist signal results to the database.

        Imports ORM models lazily to keep this module importable without a DB.
        """
        from app.models.signal import Signal, SignalSeverity

        _severity_map = {
            "low": SignalSeverity.low,
            "medium": SignalSeverity.medium,
            "high": SignalSeverity.high,
            "critical": SignalSeverity.critical,
        }

        for sr in output.signals:
            result_dict = {
                "drug": sr.drug,
                "event": sr.event,
                "a": sr.a, "b": sr.b, "c": sr.c, "d": sr.d,
                "prr": sr.prr,
                "prr_lower_ci": sr.prr_lower_ci,
                "prr_upper_ci": sr.prr_upper_ci,
                "threshold_status": sr.threshold_status.value,
                "severity": sr.severity.value,
                "rank": sr.rank,
                "algorithm_version": sr.algorithm_version,
                "disclaimer": sr.disclaimer,
            }

            sig = Signal(
                project_id=project_id,
                job_id=job_id,
                title=f"{sr.drug} — {sr.event}",
                description=(
                    f"PRR={sr.prr:.3f} (rank {sr.rank}), "
                    f"a={sr.a}, threshold={sr.threshold_status.value}"
                    if sr.prr is not None
                    else f"rank {sr.rank}, threshold={sr.threshold_status.value}"
                ),
                severity=_severity_map[sr.severity.value],
                result_json=json.dumps(result_dict),
                algorithm_version=sr.algorithm_version,
            )
            session.add(sig)

        session.commit()
