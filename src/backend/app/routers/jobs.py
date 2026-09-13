"""Jobs router — status polling and project-level job listing.

Endpoints
---------
GET /api/jobs/{job_id}                        – poll job status / result
GET /api/projects/{project_id}/jobs           – list recent jobs for a project
GET /api/projects/{project_id}/results        – recent completed results
"""
from __future__ import annotations

import json
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.shared import Job, JobStatus, JobType
from app.schemas import (
    ErrorDetail,
    ErrorEnvelope,
    JobProgress,
    JobRead,
    OkEnvelope,
)

router = APIRouter(tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


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


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}",
    response_model=OkEnvelope[JobRead],
    summary="Poll job status, progress, and result",
)
def get_job(job_id: int, session: SessionDep):
    """Retrieve the current state of a background job.

    - **QUEUED** – job is waiting to start
    - **RUNNING** – job is executing; `progress` field contains percent + message
    - **COMPLETED** – job finished; `result` field contains a summary
    - **FAILED** – job failed; `error` field contains a technical message
    """
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="JOB_NOT_FOUND", message=f"Job {job_id} not found")
            ).model_dump(),
        )
    return OkEnvelope(data=_job_to_read(job))


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/jobs
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/jobs",
    response_model=OkEnvelope[dict],
    summary="List recent jobs for a project",
)
def list_project_jobs(
    project_id: int,
    session: SessionDep,
    job_type: Optional[str] = Query(default=None, description="Filter: signal_detection | readiness_assessment"),
    job_status: Optional[str] = Query(default=None, alias="status", description="Filter: queued|running|complete|failed"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return recent jobs belonging to a project, newest first."""
    from app.models.project import Project

    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="PROJECT_NOT_FOUND", message=f"Project {project_id} not found")
            ).model_dump(),
        )

    stmt = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    if job_type:
        try:
            stmt = stmt.where(Job.job_type == JobType(job_type))
        except ValueError:
            pass
    if job_status:
        try:
            stmt = stmt.where(Job.status == JobStatus(job_status))
        except ValueError:
            pass

    all_jobs = session.exec(stmt).all()
    total = len(all_jobs)
    paged = all_jobs[offset : offset + limit]

    return OkEnvelope(
        data={
            "items": [_job_to_read(j).model_dump() for j in paged],
            "total": total,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/results  — recent completed results
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/results",
    response_model=OkEnvelope[dict],
    summary="Recent completed results for a project",
)
def list_project_results(
    project_id: int,
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return metadata for the most recent completed jobs of both types."""
    from app.models.project import Project

    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="PROJECT_NOT_FOUND", message=f"Project {project_id} not found")
            ).model_dump(),
        )

    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .where(Job.status == JobStatus.complete)
        .order_by(Job.updated_at.desc())
        .limit(limit)
    )
    jobs = session.exec(stmt).all()

    results = []
    for j in jobs:
        rd = json.loads(j.result_json) if j.result_json else {}
        results.append(
            {
                "job_id": j.id,
                "job_type": j.job_type.value,
                "completed_at": j.updated_at.isoformat(),
                "summary": rd,
            }
        )

    return OkEnvelope(data={"items": results, "total": len(results)})
