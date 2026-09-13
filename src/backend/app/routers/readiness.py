"""Submission Readiness router.

Endpoints
---------
POST   /api/projects/{project_id}/readiness/upload          – dossier outline upload + enqueue job
GET    /api/projects/{project_id}/readiness/summary          – assessment summary
GET    /api/projects/{project_id}/readiness/modules          – per-module scores
GET    /api/projects/{project_id}/readiness/requirements     – requirement matrix
GET    /api/projects/{project_id}/readiness/gaps             – gap list with filtering
GET    /api/projects/{project_id}/readiness/gaps/{gap_id}    – gap detail
PATCH  /api/projects/{project_id}/readiness/gaps/{gap_id}    – update review status
GET    /api/projects/{project_id}/readiness/export           – JSON or Markdown export
"""
from __future__ import annotations

import json
from typing import Annotated, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.readiness import (
    Gap,
    GapSeverity as GapSeverityORM,
    ReadinessAssessment,
    RequirementMapping,
    ReviewStatus as ReviewStatusORM,
)
from app.models.shared import Job, JobStatus, JobType, Upload
from app.schemas import (
    ErrorDetail,
    ErrorEnvelope,
    GapList,
    GapResult,
    GapSeverity,
    JobRead,
    JobProgress,
    ModuleScore,
    OkEnvelope,
    ReadinessAssessmentRead,
    RequirementMapping as RequirementMappingSchema,
    ReviewStatus,
    SectionStatus,
    CtdModule,
)
from app.services import audit_service
from app.services.job_runner import create_job, run_readiness_job
from app.services.upload_service import save_upload

router = APIRouter(
    prefix="/projects/{project_id}/readiness",
    tags=["readiness"],
)

SessionDep = Annotated[Session, Depends(get_session)]


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


def _latest_completed_readiness_job(project_id: int, session: Session) -> Optional[Job]:
    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.job_type == JobType.readiness_assessment)
        .where(Job.status == JobStatus.complete)
        .order_by(Job.created_at.desc())
    )
    return session.exec(stmt).first()


def _latest_assessment(project_id: int, session: Session) -> Optional[ReadinessAssessment]:
    job = _latest_completed_readiness_job(project_id, session)
    if job is None:
        return None
    stmt = (
        select(ReadinessAssessment)
        .where(ReadinessAssessment.project_id == project_id)
        .where(ReadinessAssessment.job_id == job.id)
        .order_by(ReadinessAssessment.created_at.desc())
    )
    return session.exec(stmt).first()


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


def _assessment_to_read(
    ra: ReadinessAssessment,
    session: Session,
) -> ReadinessAssessmentRead:
    # Module scores from JSON blob
    module_scores: List[ModuleScore] = []
    if ra.module_scores_json:
        try:
            for ms in json.loads(ra.module_scores_json):
                try:
                    ctd_mod = CtdModule(ms["module"])
                except (ValueError, KeyError):
                    ctd_mod = CtdModule.m3
                module_scores.append(
                    ModuleScore(
                        module=ctd_mod,
                        score=float(ms.get("score", 0.0)),
                        complete_count=int(ms.get("complete_count", 0)),
                        missing_count=int(ms.get("missing_count", 0)),
                        ambiguous_count=int(ms.get("ambiguous_count", 0)),
                        review_needed_count=int(ms.get("review_needed_count", 0)),
                        optional_count=int(ms.get("optional_count", 0)),
                    )
                )
        except Exception:
            pass

    # Gaps
    gap_rows = session.exec(
        select(Gap).where(Gap.assessment_id == ra.id)
    ).all()
    gaps = [_gap_to_schema(g) for g in gap_rows]

    # Requirement mappings
    mapping_rows = session.exec(
        select(RequirementMapping).where(RequirementMapping.assessment_id == ra.id)
    ).all()
    mappings = [
        RequirementMappingSchema(
            requirement_id=m.requirement_id,
            dossier_section_id=str(m.dossier_section_id) if m.dossier_section_id else None,
            status=SectionStatus(m.status.value),
            notes=m.notes,
        )
        for m in mapping_rows
    ]

    return ReadinessAssessmentRead(
        id=ra.id,
        project_id=ra.project_id,
        job_id=ra.job_id,
        overall_score=ra.overall_score,
        summary=ra.summary,
        module_scores=module_scores,
        gaps=gaps,
        requirement_mappings=mappings,
        review_status=ReviewStatus(ra.review_status.value),
        algorithm_version=ra.algorithm_version,
        catalog_version=ra.catalog_version,
        created_at=ra.created_at,
    )


def _gap_to_schema(g: Gap) -> GapResult:
    return GapResult(
        gap_id=g.gap_id,
        requirement_id=g.requirement_id,
        dossier_section_id=str(g.dossier_section_id) if g.dossier_section_id else None,
        description=g.description,
        severity=GapSeverity(g.severity.value),
        recommendation=g.recommendation,
        review_status=ReviewStatus(g.review_status.value),
        notes=g.notes,
    )


# ---------------------------------------------------------------------------
# POST /upload — multipart upload + enqueue job
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=OkEnvelope[JobRead],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a dossier outline CSV/JSON and start a readiness assessment",
)
async def upload_readiness_file(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    file: Optional[UploadFile] = File(default=None, description="CSV or JSON dossier outline"),
    text_input: Optional[str] = Form(default=None, description="Raw JSON/CSV text (alternative to file upload)"),
):
    """Upload a dossier outline and start a submission readiness assessment.

    Accepts either a multipart file upload or a `text_input` form field
    containing the raw JSON or CSV text.
    """
    _get_project_or_404(project_id, session)

    if file is None and not text_input:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="MISSING_INPUT",
                    message="Provide either a file upload or text_input form field.",
                )
            ).model_dump(),
        )

    if file is not None:
        content = await file.read()
        filename = file.filename or "dossier.json"
        content_type = file.content_type or "application/json"
    else:
        content = text_input.encode("utf-8")
        filename = "dossier_text_input.json"
        content_type = "application/json"

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="EMPTY_FILE", message="Uploaded content is empty.", field="file")
            ).model_dump(),
        )

    # Persist upload
    upload = save_upload(
        session,
        project_id=project_id,
        filename=filename,
        content_type=content_type,
        content=content,
        mode="readiness_assessment",
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
            "mode": "readiness_assessment",
        },
    )

    # Create job
    from app.services.readiness.catalog import CATALOG_VERSION
    from app.services.readiness.types import READINESS_ALGORITHM_VERSION
    job = create_job(
        session,
        project_id=project_id,
        job_type=JobType.readiness_assessment,
        upload_id=upload.id,
        algorithm_version=READINESS_ALGORITHM_VERSION,
        catalog_version=CATALOG_VERSION,
    )

    background_tasks.add_task(run_readiness_job, job.id, upload.id, project_id)

    return OkEnvelope(data=_job_to_read(job))


# ---------------------------------------------------------------------------
# GET /summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=OkEnvelope[ReadinessAssessmentRead],
    summary="Assessment summary for the latest completed readiness job",
)
def get_readiness_summary(project_id: int, session: SessionDep):
    _get_project_or_404(project_id, session)
    ra = _latest_assessment(project_id, session)
    if ra is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="NO_COMPLETED_ASSESSMENT",
                    message="No completed readiness assessment found for this project.",
                )
            ).model_dump(),
        )
    return OkEnvelope(data=_assessment_to_read(ra, session))


# ---------------------------------------------------------------------------
# GET /modules
# ---------------------------------------------------------------------------


@router.get(
    "/modules",
    response_model=OkEnvelope[dict],
    summary="Per-module readiness scores",
)
def get_module_scores(project_id: int, session: SessionDep):
    _get_project_or_404(project_id, session)
    ra = _latest_assessment(project_id, session)
    if ra is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="NO_COMPLETED_ASSESSMENT", message="No completed assessment found.")
            ).model_dump(),
        )
    read = _assessment_to_read(ra, session)
    return OkEnvelope(
        data={
            "assessment_id": ra.id,
            "overall_score": ra.overall_score,
            "module_scores": [ms.model_dump() for ms in read.module_scores],
        }
    )


# ---------------------------------------------------------------------------
# GET /requirements
# ---------------------------------------------------------------------------


@router.get(
    "/requirements",
    response_model=OkEnvelope[dict],
    summary="Requirement-to-dossier-section mapping matrix",
)
def get_requirement_matrix(
    project_id: int,
    session: SessionDep,
    assessment_id: Optional[int] = Query(default=None),
):
    _get_project_or_404(project_id, session)

    if assessment_id is not None:
        ra = session.get(ReadinessAssessment, assessment_id)
        if ra is None or ra.project_id != project_id:
            raise HTTPException(
                status_code=404,
                detail=ErrorEnvelope(
                    error=ErrorDetail(code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")
                ).model_dump(),
            )
    else:
        ra = _latest_assessment(project_id, session)
        if ra is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorEnvelope(
                    error=ErrorDetail(code="NO_COMPLETED_ASSESSMENT", message="No completed assessment found.")
                ).model_dump(),
            )

    mapping_rows = session.exec(
        select(RequirementMapping).where(RequirementMapping.assessment_id == ra.id)
    ).all()
    mappings = [
        {
            "requirement_id": m.requirement_id,
            "dossier_section_id": m.dossier_section_id,
            "status": m.status.value,
            "mapping_method": m.mapping_method,
            "confidence": m.confidence,
            "notes": m.notes,
        }
        for m in mapping_rows
    ]
    return OkEnvelope(
        data={
            "assessment_id": ra.id,
            "catalog_version": ra.catalog_version,
            "mappings": mappings,
            "total": len(mappings),
        }
    )


# ---------------------------------------------------------------------------
# GET /gaps
# ---------------------------------------------------------------------------


@router.get(
    "/gaps",
    response_model=OkEnvelope[GapList],
    summary="Gap list with optional filtering",
)
def list_gaps(
    project_id: int,
    session: SessionDep,
    severity: Optional[str] = Query(default=None, description="Filter: low|medium|high"),
    review_status: Optional[str] = Query(default=None, description="Filter: not_started|in_progress|approved|rejected"),
    assessment_id: Optional[int] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    _get_project_or_404(project_id, session)

    if assessment_id is not None:
        ra = session.get(ReadinessAssessment, assessment_id)
        if ra is None or ra.project_id != project_id:
            raise HTTPException(status_code=404, detail="Assessment not found")
    else:
        ra = _latest_assessment(project_id, session)
        if ra is None:
            return OkEnvelope(data=GapList(items=[], total=0))

    stmt = select(Gap).where(Gap.assessment_id == ra.id)
    if severity:
        try:
            stmt = stmt.where(Gap.severity == GapSeverityORM(severity))
        except ValueError:
            pass
    if review_status:
        try:
            stmt = stmt.where(Gap.review_status == ReviewStatusORM(review_status))
        except ValueError:
            pass

    all_gaps = session.exec(stmt).all()
    total = len(all_gaps)
    paged = all_gaps[offset : offset + limit]

    return OkEnvelope(data=GapList(items=[_gap_to_schema(g) for g in paged], total=total))


# ---------------------------------------------------------------------------
# GET /gaps/{gap_id}
# ---------------------------------------------------------------------------


@router.get(
    "/gaps/{gap_id}",
    response_model=OkEnvelope[GapResult],
    summary="Gap detail",
)
def get_gap(project_id: int, gap_id: int, session: SessionDep):
    _get_project_or_404(project_id, session)
    gap = session.get(Gap, gap_id)
    if gap is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="GAP_NOT_FOUND", message=f"Gap {gap_id} not found")
            ).model_dump(),
        )
    # Verify it belongs to this project
    ra = session.get(ReadinessAssessment, gap.assessment_id)
    if ra is None or ra.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="GAP_NOT_FOUND", message=f"Gap {gap_id} not found")
            ).model_dump(),
        )
    return OkEnvelope(data=_gap_to_schema(gap))


# ---------------------------------------------------------------------------
# PATCH /gaps/{gap_id} — update review status
# ---------------------------------------------------------------------------


class GapReviewUpdate:
    pass


from pydantic import BaseModel as _BM


class GapReviewUpdateBody(_BM):
    review_status: ReviewStatus
    notes: Optional[str] = None


@router.patch(
    "/gaps/{gap_id}",
    response_model=OkEnvelope[GapResult],
    summary="Update the review status of a gap",
)
def update_gap_review(
    project_id: int,
    gap_id: int,
    body: GapReviewUpdateBody,
    session: SessionDep,
):
    _get_project_or_404(project_id, session)
    gap = session.get(Gap, gap_id)
    if gap is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="GAP_NOT_FOUND", message=f"Gap {gap_id} not found")
            ).model_dump(),
        )
    ra = session.get(ReadinessAssessment, gap.assessment_id)
    if ra is None or ra.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="GAP_NOT_FOUND", message=f"Gap {gap_id} not found")
            ).model_dump(),
        )

    gap.review_status = ReviewStatusORM(body.review_status.value)
    if body.notes is not None:
        gap.notes = body.notes
    session.add(gap)
    session.commit()
    session.refresh(gap)

    audit_service.emit(
        session,
        event_type="gap.review_updated",
        project_id=project_id,
        detail={
            "gap_id": gap_id,
            "gap_business_id": gap.gap_id,
            "new_review_status": body.review_status.value,
        },
    )

    return OkEnvelope(data=_gap_to_schema(gap))


# ---------------------------------------------------------------------------
# GET /export — JSON or Markdown
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export readiness assessment as JSON or Markdown",
)
def export_readiness(
    project_id: int,
    session: SessionDep,
    fmt: str = Query(default="json", description="Export format: json or markdown"),
    assessment_id: Optional[int] = Query(default=None),
):
    _get_project_or_404(project_id, session)

    if assessment_id is not None:
        ra = session.get(ReadinessAssessment, assessment_id)
        if ra is None or ra.project_id != project_id:
            raise HTTPException(status_code=404, detail="Assessment not found")
    else:
        ra = _latest_assessment(project_id, session)
        if ra is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorEnvelope(
                    error=ErrorDetail(code="NO_COMPLETED_ASSESSMENT", message="No completed assessment found.")
                ).model_dump(),
            )

    read = _assessment_to_read(ra, session)

    if fmt == "markdown":
        md = _to_markdown(read)
        return Response(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=readiness_project_{project_id}.md"},
        )

    return Response(
        content=read.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=readiness_project_{project_id}.json"},
    )


def _to_markdown(ra: ReadinessAssessmentRead) -> str:
    lines = [
        f"# Submission Readiness Assessment",
        f"",
        f"**Project ID:** {ra.project_id}  ",
        f"**Assessment ID:** {ra.id}  ",
        f"**Overall Score:** {ra.overall_score * 100:.1f}%  ",
        f"**Review Status:** {ra.review_status.value}  ",
        f"**Algorithm Version:** {ra.algorithm_version}  ",
        f"",
        f"## Summary",
        f"",
        ra.summary,
        f"",
        f"## Module Scores",
        f"",
        f"| Module | Score | Complete | Missing | Review Needed |",
        f"|--------|-------|---------|---------|---------------|",
    ]
    for ms in ra.module_scores:
        lines.append(
            f"| {ms.module.value} | {ms.score * 100:.1f}% | {ms.complete_count} | {ms.missing_count} | {ms.review_needed_count} |"
        )
    lines += [
        f"",
        f"## Gaps ({len(ra.gaps)} total)",
        f"",
    ]
    for g in ra.gaps:
        lines += [
            f"### {g.gap_id} — {g.requirement_id}",
            f"",
            f"- **Severity:** {g.severity.value}",
            f"- **Review Status:** {g.review_status.value}",
            f"- **Description:** {g.description}",
            f"- **Recommendation:** {g.recommendation}",
            f"",
        ]
    return "\n".join(lines)
