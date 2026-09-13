"""FAERS-compatible CSV/JSON ingestion, schema validation, deduplication, and cleaning.

Pipeline stages (in order)
--------------------------
1. load_records()     – parse CSV or JSON into a list of raw dicts
2. validate_schema()  – check required fields present; collect errors
3. remove_exact_duplicates() – drop rows where every field is identical
4. select_latest_version()   – keep only the highest case_version per case_id
5. clean_records()    – strip whitespace, normalise empty strings to None,
                        drop rows still missing required canonical fields
6. extract_canonical()– produce CanonicalRecord objects with raw fields preserved

The six functions can be called independently for unit testing.
The full pipeline is exposed as ingest().
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Required and optional field names (FAERS column name mapping)
# ---------------------------------------------------------------------------

# Required canonical fields
_REQUIRED_FIELDS = ("case_id", "drug_raw", "event_raw")

# Column aliases: canonical name → list of accepted CSV column names (first match wins)
_COLUMN_ALIASES: Dict[str, List[str]] = {
    "primaryid":      ["primaryid"],
    "case_id":        ["caseid", "case_id"],
    "case_version":   ["caseversion", "case_version"],
    "drug_raw":       ["drugname", "drug_raw", "drug_name"],
    "event_raw":      ["event_term", "event_raw", "adverse_event"],
    "receipt_date":   ["fda_dt", "rept_dt", "receipt_date"],
    "drug_role":      ["drug_role", "role_cod"],
    "seriousness":    ["serious", "seriousness"],
    "outcome":        ["outc_cod", "outcome"],
    "age_group":      ["age_grp", "age_group"],
    "sex":            ["sex"],
    "reporter_country": ["reporter_country", "occr_country", "reporter_ctry_cod"],
}


# ---------------------------------------------------------------------------
# Canonical record dataclass
# ---------------------------------------------------------------------------


@dataclass
class CanonicalRecord:
    """One de-duplicated, cleaned case-drug-event row.

    Raw values are preserved alongside canonical fields so provenance is
    never lost.
    """

    # Required
    case_id: str
    drug_raw: str
    event_raw: str

    # Preserved optional fields
    primaryid: Optional[str] = None
    case_version: str = "1"
    receipt_date: Optional[str] = None
    drug_role: Optional[str] = None
    seriousness: Optional[str] = None
    outcome: Optional[str] = None
    age_group: Optional[str] = None
    sex: Optional[str] = None
    reporter_country: Optional[str] = None

    # Provenance: original row index in the source file (0-based)
    source_row: Optional[int] = None


# ---------------------------------------------------------------------------
# Validation error
# ---------------------------------------------------------------------------


@dataclass
class ValidationError:
    row_index: int
    field: str
    message: str


# ---------------------------------------------------------------------------
# Ingestion result
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    records: List[CanonicalRecord]
    validation_errors: List[ValidationError]
    metrics: "IngestionMetrics"


@dataclass
class IngestionMetrics:
    total_raw_rows: int = 0
    exact_duplicate_rows_removed: int = 0
    old_version_rows_removed: int = 0
    rows_after_dedup: int = 0
    rows_dropped_missing_required: int = 0
    rows_used: int = 0


# ---------------------------------------------------------------------------
# 1. Load records
# ---------------------------------------------------------------------------


def load_records(source: str | bytes, fmt: str = "csv") -> List[Dict[str, Any]]:
    """Parse CSV or JSON source into a list of raw dicts.

    Parameters
    ----------
    source:
        Raw CSV/JSON text, or bytes that will be decoded as UTF-8.
    fmt:
        "csv" or "json".  JSON must be a list of objects or a dict with
        a "records" key containing a list.

    Returns
    -------
    List of raw dicts (keys are original column names).
    """
    if isinstance(source, bytes):
        source = source.decode("utf-8")

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(source))
        return [dict(row) for row in reader]

    if fmt == "json":
        data = json.loads(source)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "records" in data:
            return data["records"]
        raise ValueError("JSON must be a list or a dict with a 'records' key.")

    raise ValueError(f"Unsupported format: {fmt!r}. Use 'csv' or 'json'.")


# ---------------------------------------------------------------------------
# 2. Schema validation
# ---------------------------------------------------------------------------


def _build_column_map(headers: List[str]) -> Dict[str, str]:
    """Build a mapping from canonical field name → actual column name found in headers.

    For each canonical field, iterate through its aliases in priority order
    and return the first one present in headers.
    """
    header_lower = {h.lower().strip(): h for h in headers}
    result: Dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in header_lower:
                result[canonical] = header_lower[alias.lower()]
                break
    return result


def validate_schema(
    rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    """Validate that required canonical fields can be mapped and are non-empty.

    Returns
    -------
    (valid_rows, errors) — both lists; errors are informational (the caller
    decides whether to abort or continue).
    """
    if not rows:
        return [], []

    col_map = _build_column_map(list(rows[0].keys()))
    errors: List[ValidationError] = []

    # Check that all required fields are mappable at all
    for req in _REQUIRED_FIELDS:
        if req not in col_map:
            # Emit a single schema-level error and return early
            errors.append(
                ValidationError(
                    row_index=-1,
                    field=req,
                    message=f"Required field '{req}' could not be mapped from column headers {list(rows[0].keys())}.",
                )
            )

    if any(e.row_index == -1 for e in errors):
        return [], errors

    valid: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        row_errors = []
        for req in _REQUIRED_FIELDS:
            col = col_map[req]
            val = str(row.get(col, "") or "").strip()
            if not val:
                row_errors.append(
                    ValidationError(
                        row_index=i,
                        field=req,
                        message=f"Row {i}: required field '{req}' (column '{col}') is empty.",
                    )
                )
        if row_errors:
            errors.extend(row_errors)
        else:
            valid.append(row)

    return valid, errors


# ---------------------------------------------------------------------------
# 3. Exact duplicate removal
# ---------------------------------------------------------------------------


def remove_exact_duplicates(
    rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int]:
    """Remove rows where every column value is identical.

    Returns
    -------
    (deduplicated_rows, count_removed)
    """
    seen: set = set()
    result: List[Dict[str, Any]] = []
    removed = 0
    for row in rows:
        key = tuple(sorted(row.items()))
        if key in seen:
            removed += 1
        else:
            seen.add(key)
            result.append(row)
    return result, removed


# ---------------------------------------------------------------------------
# 4. Latest case-version selection
# ---------------------------------------------------------------------------


def select_latest_version(
    rows: List[Dict[str, Any]],
    col_map: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], int]:
    """Keep only the row with the highest case_version for each case_id.

    If case_version is absent or not parseable as an integer, treat it as 1.

    Returns
    -------
    (latest_rows, count_removed)
    """
    case_id_col = col_map.get("case_id")
    version_col = col_map.get("case_version")

    if case_id_col is None:
        return rows, 0

    # Group: case_id → list of (version_int, row)
    groups: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    for row in rows:
        cid = str(row.get(case_id_col, "") or "").strip()
        if not cid:
            cid = "__missing__"
        if version_col:
            try:
                ver = int(str(row.get(version_col, "1") or "1").strip())
            except (ValueError, TypeError):
                ver = 1
        else:
            ver = 1
        groups.setdefault(cid, []).append((ver, row))

    result: List[Dict[str, Any]] = []
    removed = 0
    for versions in groups.values():
        max_ver = max(v for v, _ in versions)
        latest = [row for v, row in versions if v == max_ver]
        result.extend(latest)
        removed += len(versions) - len(latest)

    return result, removed


# ---------------------------------------------------------------------------
# 5. Clean records
# ---------------------------------------------------------------------------


def clean_records(
    rows: List[Dict[str, Any]],
    col_map: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], int]:
    """Strip whitespace, normalise empty strings to None.

    Rows still missing a required canonical field after cleaning are dropped.

    Returns
    -------
    (clean_rows, count_dropped)
    """
    dropped = 0
    result: List[Dict[str, Any]] = []
    for row in rows:
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        # Normalise empty strings to None
        cleaned = {k: (None if v == "" else v) for k, v in cleaned.items()}

        # Check required fields survive cleaning
        missing = False
        for req in _REQUIRED_FIELDS:
            col = col_map.get(req)
            if col is None or not cleaned.get(col):
                missing = True
                break
        if missing:
            dropped += 1
        else:
            result.append(cleaned)

    return result, dropped


# ---------------------------------------------------------------------------
# 6. Extract canonical records
# ---------------------------------------------------------------------------


def extract_canonical(
    rows: List[Dict[str, Any]],
    col_map: Dict[str, str],
) -> List[CanonicalRecord]:
    """Convert cleaned raw dicts into CanonicalRecord objects.

    Raw field values are preserved in the appropriate fields.
    """
    records: List[CanonicalRecord] = []
    for i, row in enumerate(rows):

        def _get(canonical: str, default: Optional[str] = None) -> Optional[str]:
            col = col_map.get(canonical)
            if col is None:
                return default
            val = row.get(col)
            return str(val).strip() if val is not None else default

        ver_raw = _get("case_version", "1")
        try:
            int(ver_raw)  # validate it's numeric; keep as string
        except (ValueError, TypeError):
            ver_raw = "1"

        records.append(
            CanonicalRecord(
                case_id=_get("case_id"),
                drug_raw=_get("drug_raw"),
                event_raw=_get("event_raw"),
                primaryid=_get("primaryid"),
                case_version=ver_raw or "1",
                receipt_date=_get("receipt_date"),
                drug_role=_get("drug_role"),
                seriousness=_get("seriousness"),
                outcome=_get("outcome"),
                age_group=_get("age_group"),
                sex=_get("sex"),
                reporter_country=_get("reporter_country"),
                source_row=i,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Full pipeline: ingest()
# ---------------------------------------------------------------------------


def ingest(
    source: str | bytes,
    fmt: str = "csv",
) -> IngestionResult:
    """Run the full ingestion pipeline and return an IngestionResult.

    Steps: load → validate → exact-dedup → latest-version → clean → extract.
    """
    metrics = IngestionMetrics()

    # Step 1: load
    raw_rows = load_records(source, fmt=fmt)
    metrics.total_raw_rows = len(raw_rows)

    # Step 2: validate schema (required fields must be mappable)
    valid_rows, v_errors = validate_schema(raw_rows)
    if not valid_rows and v_errors:
        return IngestionResult(records=[], validation_errors=v_errors, metrics=metrics)

    # Build the column map once (reused for later steps)
    col_map = _build_column_map(list(raw_rows[0].keys()) if raw_rows else [])

    # Step 3: exact duplicate removal
    no_exact_dups, exact_removed = remove_exact_duplicates(valid_rows)
    metrics.exact_duplicate_rows_removed = exact_removed

    # Step 4: latest case-version selection
    latest_rows, old_ver_removed = select_latest_version(no_exact_dups, col_map)
    metrics.old_version_rows_removed = old_ver_removed
    metrics.rows_after_dedup = len(latest_rows)

    # Step 5: clean
    clean_rows, dropped = clean_records(latest_rows, col_map)
    metrics.rows_dropped_missing_required = dropped
    metrics.rows_used = len(clean_rows)

    # Step 6: extract canonical
    records = extract_canonical(clean_rows, col_map)

    return IngestionResult(
        records=records,
        validation_errors=v_errors,
        metrics=metrics,
    )
