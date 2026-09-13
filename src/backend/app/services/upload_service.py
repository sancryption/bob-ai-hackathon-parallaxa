"""Upload service — handles file persistence and metadata recording.

Stores uploaded files under UPLOAD_DIR (default: ./uploads/).
Records filename, MIME type, checksum, and storage path in the uploads table.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
from typing import Optional

from sqlmodel import Session

from app.models.shared import Upload, UploadStatus

# ---------------------------------------------------------------------------
# Storage root
# ---------------------------------------------------------------------------

_UPLOAD_DIR = pathlib.Path(
    os.environ.get("UPLOAD_DIR", pathlib.Path(__file__).parent.parent.parent / "uploads")
)


def _ensure_upload_dir() -> pathlib.Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def compute_checksum(content: bytes) -> str:
    """Return the SHA-256 hex digest of *content*."""
    return hashlib.sha256(content).hexdigest()


def save_upload(
    session: Session,
    project_id: int,
    filename: str,
    content_type: str,
    content: bytes,
    mode: str = "unknown",
) -> Upload:
    """Persist file to disk, record metadata in DB, return Upload row.

    Parameters
    ----------
    session:      Active DB session.
    project_id:   Owning project.
    filename:     Original filename from the multipart upload.
    content_type: MIME type declared by the client.
    content:      Raw file bytes.
    mode:         "signal_detection" | "readiness_assessment" | "unknown"
    """
    upload_dir = _ensure_upload_dir()
    checksum = compute_checksum(content)

    # Store as <checksum>_<filename> to avoid collisions
    safe_name = f"{checksum[:12]}_{filename}"
    storage_path = upload_dir / safe_name
    storage_path.write_bytes(content)

    upload = Upload(
        project_id=project_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        status=UploadStatus.pending,
        storage_ref=str(storage_path),
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def get_upload_content(upload: Upload) -> bytes:
    """Read and return the raw bytes for a persisted upload."""
    if not upload.storage_ref:
        raise FileNotFoundError(f"Upload {upload.id} has no storage_ref")
    return pathlib.Path(upload.storage_ref).read_bytes()


def mark_upload_complete(
    session: Session,
    upload: Upload,
    row_count: Optional[int] = None,
    duplicate_count: Optional[int] = None,
) -> Upload:
    upload.status = UploadStatus.complete
    upload.row_count = row_count
    upload.duplicate_count = duplicate_count
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def mark_upload_failed(session: Session, upload: Upload) -> Upload:
    upload.status = UploadStatus.failed
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload
