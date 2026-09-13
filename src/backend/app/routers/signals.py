"""Signal Detection router.

Endpoints
---------
POST   /api/projects/{project_id}/signals/upload      – multipart upload + enqueue job
GET    /api/projects/{project_id}/signals/summary      – high-level stats after job
GET    /api/projects/{project_id}/signals               – ranked list with pagination/filtering
GET    /api/projects/{project_id}/signals/{signal_id}  – signal detail
GET    /api/projects/{project_id}/signals/clusters      – event clusters from latest job
GET    /api/projects/{project_id}/signals/export        – JSON or CSV export
"""
from __future__ import annotations

import csv as csv_mod
import io
import json
from typing import Annotated, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.shared import Job, JobStatus, JobType, Upload
from app.models.signal import Signal
from app.schemas import (
    ErrorDetail,
    ErrorEnvelope,
    EventCluster,
    JobRead,
    JobProgress,
    NormalizationProvenance,
    OkEnvelope,
    SignalList,
    SignalRead,
    SignalResult as SignalResultSchema,
    SignalSeverity,
    SignalSummary,
    SignalSummaryList,
    ThresholdStatus,
)
from app.services import audit_service
from app.services.job_runner import create_job, run_signal_job
from app.services.upload_service import save_upload

router = APIRouter(
    prefix="/projects/{project_id}/signals",
    tags=["signals"],
)

SessionDep = Annotated[Session, Depends(get_session)]

_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/json",
    "text/plain",
    "text/json",
    "application/octet-stream",  # generic fallback
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _get_project_or_404(project_id: int, session: Session):
    from app.models.project import Project

    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="PROJECT_NOT_FOUND", message=f"Project {project_id} not found")
            ).model_dump(),
        )
    return project


def _latest_completed_signal_job(project_id: int, session: Session) -> Optional[Job]:
    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.job_type == JobType.signal_detection)
        .where(Job.status == JobStatus.complete)
        .order_by(Job.created_at.desc())
    )
    return session.exec(stmt).first()


def _signal_to_read(sig: Signal) -> SignalRead:
    result = None
    if sig.result_json:
        try:
            rd = json.loads(sig.result_json)
            result = SignalResultSchema(
                drug=rd.get("drug", ""),
                event=rd.get("event", ""),
                a=rd.get("a", 0),
                b=rd.get("b", 0),
                c=rd.get("c", 0),
                d=rd.get("d", 0),
                prr=rd.get("prr", 0.0),
                prr_lower_ci=rd.get("prr_lower_ci"),
                prr_upper_ci=rd.get("prr_upper_ci"),
                threshold_status=ThresholdStatus(rd.get("threshold_status", "below")),
                severity=SignalSeverity(rd.get("severity", "low")),
                rank=rd.get("rank", 1),
                algorithm_version=rd.get("algorithm_version", "0.1.0"),
                disclaimer=rd.get("disclaimer", ""),
            )
        except Exception:
            pass
    return SignalRead(
        id=sig.id,
        project_id=sig.project_id,
        job_id=sig.job_id,
        title=sig.title,
        description=sig.description,
        severity=SignalSeverity(sig.severity.value),
        source_ref=sig.source_ref,
        result=result,
        created_at=sig.created_at,
    )


# ---------------------------------------------------------------------------
# POST /upload — multipart file upload + enqueue job
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=OkEnvelope[JobRead],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a signal detection CSV/JSON file and start a background job",
    response_description="Job queued; poll /api/jobs/{job_id} for status",
)
async def upload_signal_file(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    file: UploadFile = File(..., description="CSV or JSON file with case-level adverse event reports"),
):
    """Upload a FAERS-compatible CSV or JSON file and start signal detection.

    Returns a job ID immediately.  Poll `GET /api/jobs/{job_id}` to track
    progress.  Results appear at `GET /api/projects/{project_id}/signals`.
    """
    _get_project_or_404(project_id, session)

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="EMPTY_FILE",
                    message="Uploaded file is empty.",
                    field="file",
                )
            ).model_dump(),
        )

    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="FILE_TOO_LARGE",
                    message=f"File exceeds the 50 MB upload limit.",
                    field="file",
                )
            ).model_dump(),
        )

    content_type = file.content_type or "application/octet-stream"

    # Quick schema validation before persisting
    filename_lower = (file.filename or "").lower()
    fmt = "json" if (filename_lower.endswith(".json") or "json" in content_type) else "csv"
    _validate_signal_content(content, fmt)

    # Persist upload
    upload = save_upload(
        session,
        project_id=project_id,
        filename=file.filename or "upload",
        content_type=content_type,
        content=content,
        mode="signal_detection",
    )

    audit_service.emit(
        session,
        event_type="upload.created",
        project_id=project_id,
        detail={
            "upload_id": upload.id,
            "filename": upload.filename,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "mode": "signal_detection",
        },
    )

    # Create job
    from app.services.signal.types import ALGORITHM_VERSION
    job = create_job(
        session,
        project_id=project_id,
        job_type=JobType.signal_detection,
        upload_id=upload.id,
        algorithm_version=ALGORITHM_VERSION,
    )

    # Enqueue background task
    background_tasks.add_task(run_signal_job, job.id, upload.id, project_id)

    return OkEnvelope(data=_job_to_read(job))


def _validate_signal_content(content: bytes, fmt: str) -> None:
    """Raise 422 with structured errors if the content is obviously invalid."""
    from app.services.signal.ingestion import load_records, validate_schema

    try:
        text = content.decode("utf-8")
        rows = load_records(text, fmt=fmt)
        _valid, errors = validate_schema(rows)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="PARSE_ERROR",
                    message=f"Could not parse file as {fmt.upper()}: {exc}",
                    field="file",
                )
            ).model_dump(),
        )

    if errors and not _valid:
        # All rows invalid
        first = errors[0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=f"File failed schema validation: {first.message}",
                    field=first.field,
                    validation_errors=[
                        {"loc": [e.field or "file", str(e.row_index)], "msg": e.message, "type": "validation_error"}
                        for e in errors[:20]
                    ],
                )
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# GET /summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=OkEnvelope[dict],
    summary="High-level signal detection summary for the latest completed job",
)
def get_signal_summary(project_id: int, session: SessionDep):
    """Return aggregate counts from the most recent completed signal detection job."""
    _get_project_or_404(project_id, session)
    job = _latest_completed_signal_job(project_id, session)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="NO_COMPLETED_JOB",
                    message="No completed signal detection job found for this project.",
                )
            ).model_dump(),
        )

    signals = session.exec(
        select(Signal).where(Signal.project_id == project_id).where(Signal.job_id == job.id)
    ).all()

    result_meta = json.loads(job.result_json) if job.result_json else {}
    above = sum(1 for s in signals if s.result_json and
                json.loads(s.result_json).get("threshold_status") in ("above", "at"))

    return OkEnvelope(
        data={
            "job_id": job.id,
            "total_signals": len(signals),
            "signals_above_threshold": above,
            "rows_used": result_meta.get("rows_used"),
            "distinct_drugs": result_meta.get("distinct_drugs"),
            "algorithm_version": job.algorithm_version,
            "completed_at": job.updated_at.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# GET /  — ranked list with pagination + filtering
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=OkEnvelope[SignalSummaryList],
    summary="Ranked signal list with pagination and filtering",
)
def list_signals(
    project_id: int,
    session: SessionDep,
    job_id: Optional[int] = Query(default=None, description="Filter to a specific job"),
    severity: Optional[str] = Query(default=None, description="Filter by severity: low|medium|high|critical"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    _get_project_or_404(project_id, session)

    stmt = select(Signal).where(Signal.project_id == project_id)
    if job_id is not None:
        stmt = stmt.where(Signal.job_id == job_id)
    elif True:  # default to latest job
        latest = _latest_completed_signal_job(project_id, session)
        if latest:
            stmt = stmt.where(Signal.job_id == latest.id)

    if severity:
        from app.models.signal import SignalSeverity as SigSev
        try:
            sev_enum = SigSev(severity)
            stmt = stmt.where(Signal.severity == sev_enum)
        except ValueError:
            pass

    total_stmt = select(Signal).where(Signal.project_id == project_id)
    if job_id is not None:
        total_stmt = total_stmt.where(Signal.job_id == job_id)
    elif True:
        latest = _latest_completed_signal_job(project_id, session)
        if latest:
            total_stmt = total_stmt.where(Signal.job_id == latest.id)
    if severity:
        from app.models.signal import SignalSeverity as SigSev
        try:
            sev_enum = SigSev(severity)
            total_stmt = total_stmt.where(Signal.severity == sev_enum)
        except ValueError:
            pass
    total = len(session.exec(total_stmt).all())

    signals = session.exec(stmt.offset(offset).limit(limit)).all()

    items = []
    for sig in signals:
        rd = json.loads(sig.result_json) if sig.result_json else {}
        items.append(
            SignalSummary(
                drug=rd.get("drug", sig.title.split(" — ")[0] if " — " in sig.title else sig.title),
                event=rd.get("event", sig.title.split(" — ")[1] if " — " in sig.title else ""),
                prr=float(rd.get("prr") or 0.0),
                severity=SignalSeverity(sig.severity.value),
                threshold_status=ThresholdStatus(rd.get("threshold_status", "below")),
                rank=rd.get("rank", 1),
                total_cases=rd.get("a", 0),
            )
        )

    return OkEnvelope(data=SignalSummaryList(items=items, total=total))


# ---------------------------------------------------------------------------
# GET /clusters
# ---------------------------------------------------------------------------


@router.get(
    "/clusters",
    response_model=OkEnvelope[dict],
    summary="Event clusters from the latest completed signal detection job",
)
def get_clusters(
    project_id: int,
    session: SessionDep,
    job_id: Optional[int] = Query(default=None),
):
    """Return event normalisation clusters from the most recent completed job.

    Clusters are re-derived in-memory from the uploaded file for the
    requested job.
    """
    _get_project_or_404(project_id, session)

    if job_id is not None:
        job = session.get(Job, job_id)
    else:
        job = _latest_completed_signal_job(project_id, session)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="NO_COMPLETED_JOB", message="No completed job found.")
            ).model_dump(),
        )

    upload = session.get(Upload, job.upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    from app.services.upload_service import get_upload_content
    from app.services.signal.engine import SignalEngine

    text = get_upload_content(upload).decode("utf-8")
    fmt = "json" if upload.filename.lower().endswith(".json") else "csv"
    engine = SignalEngine()
    if fmt == "json":
        output = engine.run_from_json(text)
    else:
        output = engine.run_from_csv(text)

    clusters_out = []
    for c in output.clusters:
        clusters_out.append(
            EventCluster(
                preferred_term=c.preferred_term,
                raw_aliases=c.raw_aliases,
                meddra_code=c.meddra_code,
                case_count=c.case_count,
                provenances=[
                    NormalizationProvenance(
                        raw_term=nr.raw_term,
                        preferred_term=c.preferred_term,
                        meddra_code=c.meddra_code,
                        method=nr.method.value,
                        confidence=nr.confidence,
                    )
                    for nr in c.norm_results
                ],
            ).model_dump()
        )

    return OkEnvelope(data={"job_id": job.id, "clusters": clusters_out, "total": len(clusters_out)})


# ---------------------------------------------------------------------------
# GET /export
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export signal results as JSON or CSV",
)
def export_signals(
    project_id: int,
    session: SessionDep,
    fmt: str = Query(default="json", description="Export format: json or csv"),
    job_id: Optional[int] = Query(default=None),
):
    _get_project_or_404(project_id, session)

    if job_id is not None:
        stmt = select(Signal).where(Signal.project_id == project_id).where(Signal.job_id == job_id)
    else:
        latest = _latest_completed_signal_job(project_id, session)
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorEnvelope(
                    error=ErrorDetail(code="NO_COMPLETED_JOB", message="No completed job found.")
                ).model_dump(),
            )
        stmt = select(Signal).where(Signal.project_id == project_id).where(Signal.job_id == latest.id)

    signals = session.exec(stmt).all()

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv_mod.writer(buf)
        writer.writerow(["id", "title", "drug", "event", "prr", "a", "b", "c", "d",
                         "severity", "threshold_status", "rank", "algorithm_version"])
        for sig in signals:
            rd = json.loads(sig.result_json) if sig.result_json else {}
            writer.writerow([
                sig.id, sig.title,
                rd.get("drug", ""), rd.get("event", ""),
                rd.get("prr", ""), rd.get("a", ""), rd.get("b", ""),
                rd.get("c", ""), rd.get("d", ""),
                sig.severity.value, rd.get("threshold_status", ""),
                rd.get("rank", ""), rd.get("algorithm_version", ""),
            ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=signals_project_{project_id}.csv"},
        )

    # JSON export
    data = [_signal_to_read(sig).model_dump() for sig in signals]
    return Response(
        content=json.dumps({"project_id": project_id, "signals": data, "total": len(data)}, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=signals_project_{project_id}.json"},
    )


# ---------------------------------------------------------------------------
# GET /{signal_id}  — MUST be after all fixed-path sub-routes
# ---------------------------------------------------------------------------


@router.get(
    "/{signal_id}",
    response_model=OkEnvelope[SignalRead],
    summary="Signal detail",
)
def get_signal(project_id: int, signal_id: int, session: SessionDep):
    _get_project_or_404(project_id, session)
    sig = session.get(Signal, signal_id)
    if sig is None or sig.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="SIGNAL_NOT_FOUND", message=f"Signal {signal_id} not found")
            ).model_dump(),
        )
    return OkEnvelope(data=_signal_to_read(sig))


# ---------------------------------------------------------------------------
# Helper: Job → JobRead schema
# ---------------------------------------------------------------------------


def _job_to_read(job: Job) -> JobRead:
    progress = None
    if job.progress_json:
        try:
            pd = json.loads(job.progress_json)
            progress = JobProgress(**pd)
        except Exception:
            pass
    result = None
    if job.result_json:
        try:
            result = json.loads(job.result_json)
        except Exception:
            pass
    return JobRead(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        progress=progress,
        result=result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
