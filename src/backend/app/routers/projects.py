"""Projects router — thin handlers that delegate to ProjectService."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas import (
    ErrorDetail,
    ErrorEnvelope,
    OkEnvelope,
    ProjectCreate,
    ProjectList,
    ProjectRead,
)
from app.services.project_service import ProjectNotFoundError, ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=OkEnvelope[ProjectRead],
    status_code=status.HTTP_201_CREATED,
)
def create_project(payload: ProjectCreate, session: SessionDep):
    svc = ProjectService(session)
    project = svc.create(payload)
    return OkEnvelope(data=ProjectRead.model_validate(project))


@router.get("", response_model=OkEnvelope[ProjectList])
def list_projects(
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = ProjectService(session)
    projects, total = svc.list_all(offset=offset, limit=limit)
    return OkEnvelope(
        data=ProjectList(
            items=[ProjectRead.model_validate(p) for p in projects],
            total=total,
        )
    )


@router.get("/{project_id}", response_model=OkEnvelope[ProjectRead])
def get_project(project_id: int, session: SessionDep):
    svc = ProjectService(session)
    try:
        project = svc.get(project_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                )
            ).model_dump(),
        )
    return OkEnvelope(data=ProjectRead.model_validate(project))
