# SafetyReady — Data Contracts

Technical reference for all shared types, fixture assumptions, and validation rules.  
**Do not add product requirements or presentation content here.**

---

## Overview

All API types are defined in two authoritative files that must stay in sync:

| Layer | File |
|-------|------|
| Backend (Python) | `src/backend/app/schemas.py` |
| Frontend (TypeScript) | `src/frontend/src/types/api.ts` |

All API responses use one of two envelopes:

```
OkEnvelope<T>      { "data": T }
ErrorEnvelope      { "error": { code, message, field?, validation_errors? } }
```

---

## 1. ErrorEnvelope and ValidationDetail

```
ErrorDetail
  code:               str          — machine-readable error code (e.g. "PROJECT_NOT_FOUND")
  message:            str          — human-readable message
  field?:             str          — field path for single-field errors
  validation_errors?: ValidationDetail[]

ValidationDetail
  loc:  str[]   — field location path (e.g. ["body", "name"])
  msg:  str
  type: str     — pydantic error type (e.g. "string_too_short")
```

---

## 2. Project

```
ProjectCreate
  name:        str  (1–255 chars, required)
  description? str  (max 2000 chars)

ProjectRead
  id:           int
  name:         str
  description?: str
  status:       "draft" | "processing" | "ready" | "error"
  created_at:   datetime (ISO-8601)
  updated_at:   datetime (ISO-8601)

ProjectList
  items: ProjectRead[]
  total: int
```

---

## 3. Upload Metadata

```
UploadRead
  id:               int
  project_id:       int
  filename:         str
  content_type:     str
  size_bytes?:      int
  row_count?:       int   — set after parsing
  duplicate_count?: int   — set after deduplication
  status:           "pending" | "processing" | "complete" | "failed"
  created_at:       datetime
```

---

## 4. Job Status and Progress

```
JobProgress  (embedded in JobRead while status="running")
  percent:  float  (0.0–100.0)
  message:  str
  step:     str    — e.g. "compute_prr", "map_requirements"

JobRead
  id:          int
  project_id:  int
  job_type:    "signal_detection" | "readiness_assessment"
  status:      "queued" | "running" | "complete" | "failed"
  progress?:   JobProgress
  result?:     any   — type depends on job_type; see SignalResult / ReadinessAssessmentRead
  error?:      str
  created_at:  datetime
  updated_at:  datetime
```

---

## 5. Event Cluster and Normalization Provenance

```
NormalizationProvenance
  raw_term:       str
  preferred_term: str
  meddra_code?:   str
  method:         str    — "exact_match" | "alias_lookup" | "fuzzy"
  confidence:     float  (0.0–1.0)

EventCluster
  preferred_term: str
  raw_aliases:    str[]
  meddra_code?:   str
  case_count:     int
  provenances:    NormalizationProvenance[]
```

---

## 6. Signal Summary

Lightweight type for list views. No contingency table cells.

```
SignalSummary
  drug:             str
  event:            str
  prr:              float  (≥ 0.0)
  severity:         "low" | "medium" | "high" | "critical"
  threshold_status: "below" | "at" | "above"
  rank:             int    (≥ 1)
  total_cases:      int
```

---

## 7. Signal Result

Full disproportionality result for one drug–event pair.

```
SignalResult
  drug:             str
  event:            str
  a:                int  (≥ 0)   Drug + Event cases
  b:                int  (≥ 0)   Drug + Other-event cases
  c:                int  (≥ 0)   Other-drug + Event cases
  d:                int  (≥ 0)   Other-drug + Other-event cases
  prr:              float (≥ 0.0)   = (a/(a+b)) / (c/(c+d))
  prr_lower_ci?:    float  lower 95% CI (Poisson exact)
  prr_upper_ci?:    float  upper 95% CI
  threshold_status: "below" | "at" | "above"
  severity:         "low" | "medium" | "high" | "critical"
  rank:             int (≥ 1)
  algorithm_version: str  — semantic version of the detection engine
  disclaimer:       str  — regulatory disclaimer, must appear in every export
  event_cluster?:   EventCluster
```

PRR formula:  `PRR = (a / (a+b)) / (c / (c+d))`  
Threshold: PRR ≥ 2.0 **and** a ≥ 3 (configurable, defaults in `expected_results.json`).  
Severity mapping:
- PRR < 2: `low`
- 2 ≤ PRR < 5: `medium`
- 5 ≤ PRR < 10: `high`
- PRR ≥ 10: `critical`

---

## 8. CTD Requirement

```
CtdRequirement
  requirement_id: str    — stable ID, e.g. "CTD-3.2.S.1"
  module:         "1" | "2" | "3" | "4" | "5"
  section:        str    — e.g. "3.2.S.1"
  title:          str
  description:    str
  is_mandatory:   bool
  guidance_ref?:  str    — e.g. "ICH Q6A"
```

---

## 9. Dossier Section

```
DossierSection
  section_id:       str
  module:           "1" | "2" | "3" | "4" | "5"
  title:            str
  content_summary?: str
  status:           "complete" | "missing" | "ambiguous" | "optional" | "review_needed"
  page_ref?:        str   — filename or page reference
```

Status semantics:
| Status | Scoring | Meaning |
|--------|---------|---------|
| `complete` | 1.0 | Section present and satisfies the requirement |
| `ambiguous` | 0.5 | Section present but content is unclear or references missing data |
| `review_needed` | 0.0 (pending) | Present but requires manual review before scoring |
| `missing` | 0.0 | Required section absent |
| `optional` | excluded | Section is not mandatory; excluded from denominator |

---

## 10. Requirement Mapping

```
RequirementMapping
  requirement_id:      str
  dossier_section_id?: str   — null if no matching section found
  status:              SectionStatus
  notes?:              str
```

---

## 11. Readiness Assessment

```
ReadinessAssessmentRead
  id:                   int
  project_id:           int
  job_id:               int
  overall_score:        float (0.0–1.0)
  summary:              str
  module_scores:        ModuleScore[]
  gaps:                 GapResult[]
  requirement_mappings: RequirementMapping[]
  review_status:        "not_started" | "in_progress" | "approved" | "rejected"
  algorithm_version:    str
  created_at:           datetime
```

---

## 12. Module Score

```
ModuleScore
  module:              "1" | "2" | "3" | "4" | "5"
  score:               float (0.0–1.0)
  complete_count:      int
  missing_count:       int
  ambiguous_count:     int
  review_needed_count: int
  optional_count:      int
```

Scoring formula (per module):  
`score = (complete + 0.5 × ambiguous) / mandatory_count`  
`mandatory_count = complete + missing + ambiguous + review_needed`  
(optional sections are excluded from `mandatory_count`)

---

## 13. Gap Result

```
GapResult
  gap_id:              str
  requirement_id:      str     — must match a CtdRequirement.requirement_id
  dossier_section_id?: str
  description:         str
  severity:            "low" | "medium" | "high"
  recommendation:      str
  review_status:       ReviewStatus  (default: "not_started")
  notes?:              str
```

Gap severity assignment:
| Section status | is_mandatory | Severity |
|----------------|-------------|----------|
| `missing` | true | `high` |
| `ambiguous` | true | `medium` |
| `review_needed` | true | `medium` |
| `missing` | false | `low` |

---

## 14. Review Status

```
ReviewStatus: "not_started" | "in_progress" | "approved" | "rejected"
```

Used on `GapResult.review_status` and `ReadinessAssessmentRead.review_status`.

---

## Fixtures

### `tests/fixtures/faers_demo.csv`

Flat denormalised FAERS-style CSV (header row + 117 data rows).

| Property | Value |
|----------|-------|
| Total rows | 117 (including duplicates) |
| Unique cases after dedup | 116 |
| Drugs | DRUGALPHA, DRUGBETA, DRUGGAMMA |
| Events | headache, severe headache, nausea, liver injury, hepatic failure, fatigue, rash, vomiting |
| Multi-version case | caseid=10000001, versions 1 and 2 (engine must keep version 2) |
| Alias pairs | "headache"/"severe headache" → Headache (MedDRA 10019211) |
| | "liver injury"/"hepatic failure" → Hepatic disorder (MedDRA 10019692) |
| Strong signal | DRUGALPHA + liver injury (28 raw rows → dominant pair) |

**Deduplication rule**: for a given `caseid`, keep only the row with the highest `caseversion`. All lower versions are discarded before analysis.

### `tests/fixtures/dossier_outline.json`

| Property | Value |
|----------|-------|
| Requirements | 18 |
| Sections | 18 |
| complete | 8 |
| missing | 3 (CTD-1.3.2, CTD-3.2.S.3, CTD-5.3.1) |
| ambiguous | 3 (CTD-2.5, CTD-2.6, CTD-3.2.S.2) |
| optional | 4 (CTD-3.2.P.2, CTD-4.2.3, CTD-5.3.6 + SEC-4.2.3 optional) |
| review_needed | 1 (CTD-1.3.1 SmPC draft) |
| Modules | 1, 2, 3, 4, 5 all represented |

### `tests/fixtures/expected_results.json`

Specifies acceptable ranges (not hard values) for engine outputs:

| Metric | Expected |
|--------|----------|
| PRR for DRUGALPHA+HepaticDisorder | ≥ 5.0 |
| Threshold status | above |
| Overall readiness score | 0.45–0.75 |
| Gap count | 6–8 |
| Mandatory missing gaps severity | high |

---

## Column reference — faers_demo.csv

| Column | Type | Description |
|--------|------|-------------|
| `primaryid` | int | Unique report identifier |
| `caseid` | int | Patient case identifier (shared across versions) |
| `caseversion` | str | Version number; higher = more recent |
| `i_f_code` | str | Initial/Follow-up indicator |
| `event_dt` | str | Event date (YYYYMMDD) |
| `mfr_dt` | str | Manufacturer receipt date |
| `init_fda_dt` | str | Initial FDA date |
| `fda_dt` | str | Current FDA date |
| `rept_cod` | str | Report code |
| `mfr_sndr` | str | Manufacturer sender name |
| `age` | int | Patient age |
| `age_cod` | str | Age unit (YR) |
| `age_grp` | str | Age group (A=adult, E=elderly, T=teen) |
| `sex` | str | Patient sex (M/F/UNK) |
| `wt` | int | Patient weight |
| `wt_cod` | str | Weight unit (KG) |
| `occp_cod` | str | Reporter occupation code |
| `reporter_country` | str | Reporter country |
| `occr_country` | str | Occurrence country |
| `drugname` | str | Drug name (denormalised) |
| `event_term` | str | Adverse event term (raw, may be alias) |
