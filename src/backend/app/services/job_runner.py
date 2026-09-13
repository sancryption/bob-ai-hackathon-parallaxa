"""Job runner service — in-process background job execution.

Uses FastAPI BackgroundTasks to run signal detection and readiness
assessment jobs without Redis, Celery, or any external queue.

Job lifecycle
-------------
QUEUED  → created; task has been enqueued with BackgroundTasks
RUNNING → execution started; progress_json updated periodically
COMPLETED → result_json populated; signals/assessments persisted
FAILED  → error field populated; result_json is None
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlmodel import Session, create_engine

from app.config import settings
from app.models.shared import Job, JobStatus, JobType, Upload
from app.services import audit_service

# ---------------------------------------------------------------------------
# Engine factory — overridable in tests
# ---------------------------------------------------------------------------
# Tests replace this with a factory that returns the test engine so that
# background jobs write to the same in-memory database.

_engine_factory: Optional[Callable] = None


def set_engine_factory(factory: Optional[Callable]) -> None:
    """Set a custom engine factory for testing.

    Call ``set_engine_factory(lambda: test_engine)`` before running tests,
    and ``set_engine_factory(None)`` to restore the default behaviour.
    """
    global _engine_factory
    _engine_factory = factory


def _get_engine():
    if _engine_factory is not None:
        return _engine_factory()
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------


def _set_progress(session: Session, job: Job, percent: float, message: str, step: str) -> None:
    """Update job progress snapshot in-place and commit."""
    job.progress_json = json.dumps({"percent": percent, "message": message, "step": step})
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()


def _set_running(session: Session, job: Job) -> None:
    job.status = JobStatus.running
    _set_progress(session, job, 0.0, "Job started", "init")


def _set_completed(session: Session, job: Job, result: dict) -> None:
    job.status = JobStatus.complete
    job.result_json = json.dumps(result)
    job.progress_json = json.dumps({"percent": 100.0, "message": "Completed", "step": "done"})
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()


def _set_failed(session: Session, job: Job, error_msg: str) -> None:
    job.status = JobStatus.failed
    job.error = error_msg[:4096]
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()


# ---------------------------------------------------------------------------
# Signal detection job
# ---------------------------------------------------------------------------


def run_signal_job(job_id: int, upload_id: int, project_id: int) -> None:
    """Run the signal detection pipeline for *job_id*.

    Creates a fresh DB session (runs in a background thread, not the
    request context).
    """
    with Session(_get_engine()) as session:
        job = session.get(Job, job_id)
        if job is None:
            return

        try:
            _set_running(session, job)

            # 1. Fetch upload content
            _set_progress(session, job, 10.0, "Loading uploaded file", "load")
            upload = session.get(Upload, upload_id)
            if upload is None:
                raise ValueError(f"Upload {upload_id} not found")

            from app.services.upload_service import get_upload_content
            content = get_upload_content(upload)
            text = content.decode("utf-8")

            # 2. Detect format
            _set_progress(session, job, 20.0, "Detecting file format", "detect_format")
            fmt = "csv" if upload.content_type in ("text/csv", "application/csv") else "json"
            if upload.filename.lower().endswith(".json"):
                fmt = "json"
            elif upload.filename.lower().endswith(".csv"):
                fmt = "csv"

            # 3. Run engine
            _set_progress(session, job, 30.0, "Running signal detection algorithm", "detect")
            from app.services.signal.engine import SignalEngine, SignalEngineConfig
            engine_cfg = SignalEngineConfig()
            engine_svc = SignalEngine(engine_cfg)

            if fmt == "json":
                output = engine_svc.run_from_json(text)
            else:
                output = engine_svc.run_from_csv(text)

            _set_progress(session, job, 70.0, "Persisting signals to database", "persist")

            # 4. Persist signals
            engine_svc._persist(output, session, project_id, job_id, upload_id)

            # 5. Update upload metadata
            from app.services.upload_service import mark_upload_complete
            mark_upload_complete(
                session,
                upload,
                row_count=output.metrics.rows_used,
                duplicate_count=output.metrics.exact_duplicate_rows_removed,
            )

            _set_progress(session, job, 90.0, "Finalising results", "finalise")

            # 6. Build result summary
            result = {
                "signals_detected": len(output.signals),
                "pairs_above_threshold": output.metrics.pairs_above_threshold,
                "rows_used": output.metrics.rows_used,
                "total_raw_rows": output.metrics.total_raw_rows,
                "exact_duplicate_rows_removed": output.metrics.exact_duplicate_rows_removed,
                "rows_dropped_missing_required": output.metrics.rows_dropped_missing_required,
                "distinct_drugs": output.metrics.distinct_drugs,
                "distinct_events_canonical": output.metrics.distinct_events_canonical,
                "algorithm_version": output.metrics.algorithm_version,
            }

            _set_completed(session, job, result)

            # 7. Audit
            audit_service.emit(
                session,
                event_type="job.completed",
                project_id=project_id,
                job_id=job_id,
                detail={
                    "job_type": "signal_detection",
                    "upload_id": upload_id,
                    "algorithm_version": engine_cfg.algorithm_version,
                    "signals_detected": len(output.signals),
                },
            )

        except Exception as exc:
            tb = traceback.format_exc()
            # Exclude raw traceback from the public error message but keep it logged
            safe_msg = f"{type(exc).__name__}: {exc}"
            # Refresh job in case of partial commit
            try:
                session.rollback()
                job = session.get(Job, job_id)
                if job:
                    _set_failed(session, job, safe_msg)
                    audit_service.emit(
                        session,
                        event_type="job.failed",
                        project_id=project_id,
                        job_id=job_id,
                        detail={"error": safe_msg, "job_type": "signal_detection"},
                    )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Readiness assessment job
# ---------------------------------------------------------------------------


def run_readiness_job(job_id: int, upload_id: int, project_id: int) -> None:
    """Run the readiness assessment pipeline for *job_id*."""
    with Session(_get_engine()) as session:
        job = session.get(Job, job_id)
        if job is None:
            return

        try:
            _set_running(session, job)

            # 1. Fetch upload content
            _set_progress(session, job, 10.0, "Loading uploaded dossier outline", "load")
            upload = session.get(Upload, upload_id)
            if upload is None:
                raise ValueError(f"Upload {upload_id} not found")

            from app.services.upload_service import get_upload_content
            content = get_upload_content(upload)
            text = content.decode("utf-8")

            # 2. Detect format
            _set_progress(session, job, 20.0, "Detecting file format", "detect_format")
            fmt = "json"
            if upload.filename.lower().endswith(".csv") or upload.content_type in (
                "text/csv", "application/csv"
            ):
                fmt = "csv"
            elif upload.filename.lower().endswith(".txt"):
                fmt = "text"

            # 3. Run engine
            _set_progress(session, job, 30.0, "Running readiness assessment algorithm", "assess")
            from app.services.readiness.engine import ReadinessEngine, ReadinessEngineConfig
            engine_cfg = ReadinessEngineConfig()
            engine_svc = ReadinessEngine(engine_cfg)

            output = engine_svc._run(text, fmt=fmt)

            _set_progress(session, job, 70.0, "Persisting assessment to database", "persist")

            # 4. Persist
            engine_svc._persist(output, session, project_id, job_id, upload_id)

            # 5. Update upload metadata
            from app.services.upload_service import mark_upload_complete
            mark_upload_complete(session, upload)

            _set_progress(session, job, 90.0, "Finalising results", "finalise")

            # 6. Build result summary
            result = {
                "overall_score": output.overall_score,
                "gap_count": len(output.gaps),
                "module_count": len(output.module_scores),
                "algorithm_version": output.algorithm_version,
                "catalog_version": output.catalog_version,
            }

            _set_completed(session, job, result)

            # 7. Audit
            audit_service.emit(
                session,
                event_type="job.completed",
                project_id=project_id,
                job_id=job_id,
                detail={
                    "job_type": "readiness_assessment",
                    "upload_id": upload_id,
                    "algorithm_version": engine_cfg.algorithm_version,
                    "catalog_version": engine_cfg.catalog_version,
                    "overall_score": output.overall_score,
                    "gap_count": len(output.gaps),
                },
            )

        except Exception as exc:
            safe_msg = f"{type(exc).__name__}: {exc}"
            try:
                session.rollback()
                job = session.get(Job, job_id)
                if job:
                    _set_failed(session, job, safe_msg)
                    audit_service.emit(
                        session,
                        event_type="job.failed",
                        project_id=project_id,
                        job_id=job_id,
                        detail={"error": safe_msg, "job_type": "readiness_assessment"},
                    )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Job creation helper (called from route handlers)
# ---------------------------------------------------------------------------


def create_job(
    session: Session,
    project_id: int,
    job_type: JobType,
    upload_id: Optional[int] = None,
    algorithm_version: str = "0.1.0",
    catalog_version: Optional[str] = None,
) -> Job:
    """Create a QUEUED job row and return it."""
    job = Job(
        project_id=project_id,
        upload_id=upload_id,
        job_type=job_type,
        status=JobStatus.queued,
        algorithm_version=algorithm_version,
        catalog_version=catalog_version,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    audit_service.emit(
        session,
        event_type="job.queued",
        project_id=project_id,
        job_id=job.id,
        detail={
            "job_type": job_type.value,
            "upload_id": upload_id,
            "algorithm_version": algorithm_version,
            "catalog_version": catalog_version,
        },
    )

    return job
