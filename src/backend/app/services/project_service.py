"""Project service — all project domain logic lives here.

Route handlers delegate to this module so they stay thin.
Future engines (Signal Detection, Readiness Assessment) will each get their
own service module alongside this one.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from app.models.project import Project
from app.schemas import ProjectCreate, ProjectStatus


class ProjectNotFoundError(Exception):
    pass


class ProjectService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: ProjectCreate) -> Project:
        project = Project(
            name=payload.name,
            description=payload.description,
        )
        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project

    def get(self, project_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project {project_id} not found")
        return project

    def list_all(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[List[Project], int]:
        total = len(self._session.exec(select(Project)).all())
        projects = self._session.exec(
            select(Project).offset(offset).limit(limit)
        ).all()
        return list(projects), total

    def update_status(self, project_id: int, status: ProjectStatus) -> Project:
        project = self.get(project_id)
        project.status = status
        project.updated_at = datetime.now(timezone.utc)
        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project
