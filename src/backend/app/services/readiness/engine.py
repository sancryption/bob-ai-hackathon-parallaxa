"""ReadinessEngine — orchestrates the complete submission readiness pipeline.

Pipeline
--------
parse_outline() →  map_requirements() →  score_all_modules() →
score_overall() →  generate_gaps() →  (optional) persist_to_db()

Usage (pure / no DB)
--------------------
    from app.services.readiness.engine import ReadinessEngine, ReadinessEngineConfig

    output = ReadinessEngine().run_from_json(json_text)

Usage (with DB persistence)
---------------------------
    output = ReadinessEngine(config).run_and_persist(
        json_text, session, project_id, job_id, upload_id
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.readiness.catalog import (
    CATALOG_VERSION,
    build_catalog,
)
from app.services.readiness.gaps import generate_gaps
from app.services.readiness.mapper import map_requirements
from app.services.readiness.parser import parse_outline
from app.services.readiness.scorer import score_all_modules, score_overall
from app.services.readiness.types import (
    READINESS_ALGORITHM_VERSION,
    READINESS_DISCLAIMER,
    MappingResult,
    ModuleScoreResult,
    ReadinessOutput,
    RequirementRecord,
    SectionReadinessStatus,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ReadinessEngineConfig:
    """Top-level configuration for one readiness assessment run."""

    catalog_version: str = CATALOG_VERSION
    algorithm_version: str = READINESS_ALGORITHM_VERSION
    # Optional per-requirement status overrides (e.g. not_applicable)
    override_status: Dict[str, SectionReadinessStatus] = field(default_factory=dict)
    # Additional catalog requirements to supplement the built-in catalog
    extra_requirements: List[RequirementRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ReadinessEngine
# ---------------------------------------------------------------------------


class ReadinessEngine:
    """Deterministic submission readiness assessment engine.

    All computations are pure and reproducible given the same input.
    """

    def __init__(self, config: Optional[ReadinessEngineConfig] = None) -> None:
        self._config = config or ReadinessEngineConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_from_json(self, json_text: str) -> ReadinessOutput:
        """Run the full pipeline on a JSON dossier outline."""
        return self._run(json_text, fmt="json")

    def run_from_csv(self, csv_text: str) -> ReadinessOutput:
        """Run the full pipeline on a CSV dossier outline."""
        return self._run(csv_text, fmt="csv")

    def run_and_persist(
        self,
        json_text: str,
        session,
        project_id: int,
        job_id: int,
        upload_id: Optional[int] = None,
    ) -> ReadinessOutput:
        """Run the pipeline and persist assessment results to the database."""
        output = self.run_from_json(json_text)
        self._persist(output, session, project_id, job_id, upload_id)
        return output

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run(self, source: str, fmt: str = "json") -> ReadinessOutput:
        cfg = self._config

        # 1. Parse dossier outline
        sections = parse_outline(source, fmt=fmt)

        # 2. Load catalog
        catalog = build_catalog(cfg.catalog_version)
        if cfg.extra_requirements:
            catalog = catalog + cfg.extra_requirements

        # 3. Map requirements to sections
        mappings = map_requirements(
            catalog,
            sections,
            override_status=cfg.override_status or None,
        )

        # 4. Score modules
        module_scores = score_all_modules(catalog, mappings, cfg.catalog_version)

        # 5. Overall score
        overall = score_overall(module_scores)

        # 6. Generate gaps
        gaps = generate_gaps(catalog, mappings)

        # 7. Summary text
        summary = self._build_summary(overall, module_scores, gaps)

        return ReadinessOutput(
            overall_score=overall,
            summary=summary,
            module_scores=module_scores,
            mappings=mappings,
            gaps=gaps,
            algorithm_version=cfg.algorithm_version,
            catalog_version=cfg.catalog_version,
            disclaimer=READINESS_DISCLAIMER,
        )

    @staticmethod
    def _build_summary(
        overall: float,
        module_scores: List[ModuleScoreResult],
        gaps: list,
    ) -> str:
        high_gaps = sum(1 for g in gaps if g.severity.value == "high")
        medium_gaps = sum(1 for g in gaps if g.severity.value == "medium")
        pct = round(overall * 100, 1)
        lines = [
            f"Overall readiness score: {pct}%.",
            f"High-priority gaps: {high_gaps}.  Medium-priority gaps: {medium_gaps}.",
        ]
        for ms in module_scores:
            lines.append(
                f"Module {ms.module}: score={round(ms.score * 100, 1)}%  "
                f"(complete={ms.complete_count}, "
                f"review_needed={ms.present_needs_review_count}, "
                f"missing={ms.missing_count})."
            )
        return "  ".join(lines)

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _persist(
        self,
        output: ReadinessOutput,
        session,
        project_id: int,
        job_id: int,
        upload_id: Optional[int],
    ) -> None:
        """Persist the assessment to the database.

        Imports ORM models lazily to keep this module importable without a DB.
        """
        from app.models.readiness import (
            Gap as GapORM,
            GapSeverity as GapSeverityORM,
            ReadinessAssessment as ReadinessAssessmentORM,
            RequirementMapping as RequirementMappingORM,
            ReviewStatus as ReviewStatusORM,
            SectionStatus as SectionStatusORM,
        )

        # Build module_scores_json
        module_scores_data = [
            {
                "module": ms.module,
                "score": ms.score,
                "complete_count": ms.complete_count,
                "missing_count": ms.missing_count,
                "ambiguous_count": ms.present_needs_review_count,
                "review_needed_count": ms.present_needs_review_count,
                "optional_count": ms.optional_not_submitted_count,
            }
            for ms in output.module_scores
        ]

        ra = ReadinessAssessmentORM(
            project_id=project_id,
            job_id=job_id,
            upload_id=upload_id,
            overall_score=output.overall_score,
            summary=output.summary[:4096],
            module_scores_json=json.dumps(module_scores_data),
            algorithm_version=output.algorithm_version,
            catalog_version=output.catalog_version,
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        # Persist mappings
        _section_status_map = {
            "complete": SectionStatusORM.complete,
            "present_needs_review": SectionStatusORM.review_needed,
            "missing": SectionStatusORM.missing,
            "not_applicable": SectionStatusORM.optional,
            "optional_not_submitted": SectionStatusORM.optional,
        }
        for m in output.mappings:
            orm_status = _section_status_map.get(m.status.value, SectionStatusORM.review_needed)
            rm = RequirementMappingORM(
                assessment_id=ra.id,
                requirement_id=m.requirement_id,
                status=orm_status,
                notes=m.notes,
            )
            session.add(rm)

        # Persist gaps
        _sev_map = {
            "low": GapSeverityORM.low,
            "medium": GapSeverityORM.medium,
            "high": GapSeverityORM.high,
        }
        for g in output.gaps:
            orm_gap = GapORM(
                assessment_id=ra.id,
                gap_id=g.gap_id,
                requirement_id=g.requirement_id,
                description=g.description[:4096],
                severity=_sev_map.get(g.severity.value, GapSeverityORM.medium),
                recommendation=g.recommendation[:4096],
            )
            session.add(orm_gap)

        session.commit()
