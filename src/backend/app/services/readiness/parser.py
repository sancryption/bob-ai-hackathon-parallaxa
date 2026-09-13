"""Dossier outline parser.

Supported input formats
-----------------------
* JSON outline  – the canonical format used by the fixture (dossier_outline.json).
  Accepts a top-level "sections" list, or a flat list of section objects.
* CSV outline   – a CSV with columns: section_id, module, title,
                  content_summary, status, page_ref.
* Text (stub)   – a plain-text adapter that returns an empty list; actual
                  OCR / text parsing is out of scope and must be provided
                  by a caller-supplied pre-processor.

The parser is format-agnostic: callers always receive List[DossierSectionRecord].

Section code extraction
-----------------------
The section_id in the fixture follows the pattern "SEC-<code>" (e.g. "SEC-3.2.S.1").
The parser strips the "SEC-" prefix to obtain the normalised section_code.
If the section_id does not carry the "SEC-" prefix it is used as-is.
The module_hint is inferred from the first character of the section_code.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Dict, List, Optional

from app.services.readiness.types import DossierSectionRecord


# ---------------------------------------------------------------------------
# Section-code normalisation helpers
# ---------------------------------------------------------------------------

_SEC_PREFIX_RE = re.compile(r"^SEC-", re.IGNORECASE)


def _extract_code(section_id: str) -> str:
    """Strip 'SEC-' prefix and return the bare section code."""
    return _SEC_PREFIX_RE.sub("", section_id.strip())


def _infer_module(section_code: str) -> str:
    """Infer the CTD module number from the section code.

    Examples
    --------
    "3.2.S.1" → "3"
    "1.3.2"   → "1"
    "5.3.5"   → "5"
    """
    code = section_code.strip()
    if code:
        return code[0]
    return ""


def _status_to_content_present(status: str) -> bool:
    """Return True if the status implies content is physically present."""
    return status.strip().lower() not in ("missing", "optional_not_submitted")


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------


def _parse_section_obj(
    obj: Dict[str, Any], source: str = "json_outline"
) -> DossierSectionRecord:
    """Convert a single section dict into a DossierSectionRecord."""
    section_id: str = str(obj.get("section_id") or obj.get("id") or "")
    section_code = _extract_code(section_id) if section_id else ""
    # Allow an explicit section_code override
    if "section_code" in obj and obj["section_code"]:
        section_code = str(obj["section_code"]).strip()

    module_hint = str(obj.get("module") or _infer_module(section_code))
    title = str(obj.get("title") or "")
    summary_raw = obj.get("content_summary") or obj.get("summary")
    summary = str(summary_raw).strip() if summary_raw else None
    raw_status = str(obj.get("status") or "unknown").strip().lower()
    page_ref = obj.get("page_ref") or obj.get("page_reference")
    content_present = _status_to_content_present(raw_status)

    return DossierSectionRecord(
        section_id=section_id,
        module_hint=module_hint,
        section_code=section_code,
        title=title,
        summary=summary,
        content_present=content_present,
        source=source,
        raw_status=raw_status,
        page_ref=str(page_ref).strip() if page_ref else None,
    )


def parse_json_outline(
    source: str | bytes,
    source_label: str = "json_outline",
) -> List[DossierSectionRecord]:
    """Parse a JSON dossier outline into DossierSectionRecord objects.

    Accepts:
    - {"sections": [...], ...}  – canonical fixture format
    - {"records": [...]}        – generic wrapper
    - [...]                     – bare list
    """
    if isinstance(source, bytes):
        source = source.decode("utf-8")

    data = json.loads(source)

    if isinstance(data, list):
        section_dicts = data
    elif isinstance(data, dict):
        if "sections" in data:
            section_dicts = data["sections"]
        elif "records" in data:
            section_dicts = data["records"]
        else:
            # Treat the whole dict as a single section (edge case)
            section_dicts = [data]
    else:
        return []

    return [_parse_section_obj(obj, source=source_label) for obj in section_dicts]


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

_CSV_COLUMN_MAP = {
    # canonical name : accepted column aliases (priority order)
    "section_id":      ["section_id", "id", "sec_id"],
    "module":          ["module", "module_number", "ctd_module"],
    "title":           ["title", "section_title", "name"],
    "content_summary": ["content_summary", "summary", "description", "content"],
    "status":          ["status", "section_status", "readiness_status"],
    "page_ref":        ["page_ref", "page_reference", "file_ref", "filename"],
    "section_code":    ["section_code", "code"],
}


def _csv_col_map(headers: List[str]) -> Dict[str, str]:
    """Build canonical → actual column name mapping for the given headers."""
    lower_map = {h.lower().strip(): h for h in headers}
    result: Dict[str, str] = {}
    for canonical, aliases in _CSV_COLUMN_MAP.items():
        for alias in aliases:
            if alias.lower() in lower_map:
                result[canonical] = lower_map[alias.lower()]
                break
    return result


def parse_csv_outline(
    source: str | bytes,
    source_label: str = "csv_outline",
) -> List[DossierSectionRecord]:
    """Parse a CSV dossier outline into DossierSectionRecord objects."""
    if isinstance(source, bytes):
        source = source.decode("utf-8")

    reader = csv.DictReader(io.StringIO(source))
    rows = list(reader)
    if not rows:
        return []

    col_map = _csv_col_map(list(rows[0].keys()))

    def _get(row: Dict, key: str, default: str = "") -> str:
        col = col_map.get(key)
        if col is None:
            return default
        val = row.get(col)
        return str(val).strip() if val else default

    records: List[DossierSectionRecord] = []
    for row in rows:
        section_id = _get(row, "section_id")
        # Explicit section_code overrides extraction from section_id
        explicit_code = _get(row, "section_code")
        section_code = explicit_code if explicit_code else _extract_code(section_id)
        module_hint = _get(row, "module") or _infer_module(section_code)
        title = _get(row, "title")
        raw_status = _get(row, "status", "unknown").lower()
        summary_raw = _get(row, "content_summary")
        summary = summary_raw if summary_raw else None
        page_ref_raw = _get(row, "page_ref")
        page_ref = page_ref_raw if page_ref_raw else None
        content_present = _status_to_content_present(raw_status)

        records.append(
            DossierSectionRecord(
                section_id=section_id,
                module_hint=module_hint,
                section_code=section_code,
                title=title,
                summary=summary,
                content_present=content_present,
                source=source_label,
                raw_status=raw_status,
                page_ref=page_ref,
            )
        )

    return records


# ---------------------------------------------------------------------------
# Text adapter (stub)
# ---------------------------------------------------------------------------


def parse_text_outline(
    source: str | bytes,
    source_label: str = "text",
) -> List[DossierSectionRecord]:
    """Stub text/PDF adapter.

    OCR and unstructured text parsing are not requirements for the MVP.
    Callers must pre-process unstructured text into JSON or CSV before
    passing it to this module.  This stub returns an empty list and can
    be replaced with a full implementation behind this adapter boundary.
    """
    return []


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------


def parse_outline(
    source: str | bytes,
    fmt: str = "json",
    source_label: Optional[str] = None,
) -> List[DossierSectionRecord]:
    """Parse a dossier outline in the given format.

    Parameters
    ----------
    source:
        Raw text or bytes.
    fmt:
        "json" | "csv" | "text"
    source_label:
        Optional provenance label stored on every returned record.
    """
    label = source_label or fmt
    if fmt == "json":
        return parse_json_outline(source, source_label=label)
    if fmt == "csv":
        return parse_csv_outline(source, source_label=label)
    if fmt == "text":
        return parse_text_outline(source, source_label=label)
    raise ValueError(f"Unsupported dossier outline format: {fmt!r}. Use 'json', 'csv', or 'text'.")
