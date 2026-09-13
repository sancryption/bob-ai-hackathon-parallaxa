"""Audit service — write immutable audit events to the audit_events table."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlmodel import Session

from app.models.shared import AuditEvent


def emit(
    session: Session,
    event_type: str,
    project_id: Optional[int] = None,
    job_id: Optional[int] = None,
    actor: Optional[str] = "system",
    detail: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Insert one audit event and commit.

    Parameters
    ----------
    session:     Active DB session.
    event_type:  Dot-separated string, e.g. "upload.created", "job.completed".
    project_id:  Optional owning project ID.
    job_id:      Optional associated job ID.
    actor:       Free-form actor label (defaults to "system").
    detail:      Arbitrary dict serialised to JSON and stored in detail_json.
    """
    event = AuditEvent(
        project_id=project_id,
        job_id=job_id,
        event_type=event_type,
        actor=actor,
        detail_json=json.dumps(detail) if detail else None,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
