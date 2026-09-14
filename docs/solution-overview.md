# Solution Overview

## What We Built

SafetyReady is a full-stack web application that gives pharmaceutical analysts a self-contained tool for two regulatory workflows: pharmacovigilance signal detection from adverse-event data, and ICH CTD submission readiness assessment from a dossier outline. Both workflows are fully deterministic — given the same input, they always produce the same output — and run entirely offline with no external API dependencies.

---

## How It Works

### Workflow 1 — Signal Detection

1. **Upload:** The analyst creates a project and uploads a FAERS-style adverse-event file (CSV or JSON) containing fields such as `case_id`, `caseversion`, `drugname`, and `event_term`. The file may be raw denormalised data with duplicates across case versions.

2. **Ingestion and deduplication:** The engine parses the file, removes exact-duplicate rows, and for any `case_id` with multiple versions keeps only the row with the highest `caseversion` — matching the FDA's own deduplication rule for FAERS data.

3. **Normalisation and clustering:** Each raw drug name and adverse-event string is normalised using a two-step strategy: first an exact alias dictionary look-up (e.g., "liver injury" → `Hepatic disorder / MedDRA 10019692`), then a rapidfuzz `token_set_ratio` fuzzy match against known MedDRA preferred terms (threshold ≥ 0.90). The engine tracks normalisation provenance (method + confidence) for every term, and groups raw aliases that resolve to the same preferred term into event clusters.

4. **Contingency tables:** For every (canonical drug, canonical event) pair, the engine computes the standard 2×2 contingency table: `a` (drug+event), `b` (drug+other event), `c` (other drug+event), `d` (other drug+other event).

5. **PRR computation:** `PRR = [a / (a+b)] / [c / (c+d)]`. 95% confidence intervals are computed using the Evans (2001) log-normal approximation: `exp(ln(PRR) ± 1.96 × SE)` where `SE = sqrt(1/a − 1/(a+b) + 1/c − 1/(c+d))`.

6. **Threshold filtering and ranking:** Pairs are filtered to those meeting all four thresholds: `a ≥ 3`, `(a+b) ≥ 5`, `(a+c) ≥ 3`, and `PRR ≥ 2.0`. Passing pairs are assigned a severity level (critical ≥ 8.0, high ≥ 4.0, medium ≥ 2.0) and ranked by status, PRR descending, pair count descending, and seriousness count.

7. **Results:** The frontend shows a ranked signal table with severity badges, filterable by severity and sortable by rank/PRR/case count. Clicking a signal opens a detail panel with the full 2×2 table, PRR value, CI, cluster membership, and algorithm version. Results are exportable as JSON or CSV.

### Workflow 2 — Submission Readiness Assessment

1. **Upload:** The analyst uploads a structured dossier outline — a JSON or CSV file listing the sections that exist in their draft dossier, with each section's `section_code`, `title`, and a `status` field (`complete`, `review_needed`, `ambiguous`, `missing`, or `optional`).

2. **Catalog loading:** The engine loads a versioned ICH CTD requirements catalog (version `0.1.0`). The catalog contains 20 representative requirements covering all five CTD modules, each with a `section_code`, `title`, `requiredness` (mandatory/optional), `keywords`, `weight`, and ICH guidance reference.

3. **4-tier requirement mapping:** Each catalog requirement is matched against the uploaded dossier sections using four tiers in priority order:
   - **Tier 1 — Exact code:** `section_code` from the dossier exactly equals the requirement's `section_code`
   - **Tier 2 — Normalised code:** both codes lowercased with dots/spaces/dashes removed
   - **Tier 3 — Keyword/title:** the dossier section's title or summary contains ≥ 2 catalog keywords, or ≥ 1 keyword of 8+ characters
   - **Tier 4 — Fuzzy title:** rapidfuzz `token_set_ratio` ≥ 0.85 between the requirement title and the section title

4. **Status resolution:** For matched sections, the raw dossier status drives the readiness status: `complete` → score 1.0, `review_needed` / `ambiguous` → `present_needs_review` (score 0.5), `missing` → score 0.0. Unmatched mandatory requirements are counted as missing; unmatched optional requirements are counted as `optional_not_submitted`.

5. **Module scoring:** Each CTD module is scored independently. Only mandatory requirements contribute to the denominator. Formula: `score = sum(weight × credit) / sum(weight)` over applicable mandatory requirements for that module.

6. **Overall score and gap generation:** The overall score is the equal-weight mean of module scores. A gap record is generated for every mandatory requirement with status `missing`, `ambiguous`, or `review_needed`, with a severity assignment (`high` for missing mandatory, `medium` for ambiguous/review-needed mandatory) and a template-driven recommendation.

7. **Results:** The frontend shows an overall score bar, per-module score cards, a gap table filterable by severity and module, a requirement mapping matrix showing match method and confidence, and JSON/Markdown export.

---

## Architecture Diagram

See [`architecture.md`](architecture.md) for the detailed Mermaid diagram and component table.

```
[Browser] → [React 19 SPA] → [FastAPI REST API] → [SQLite DB]
                                      ↓
                              [BackgroundTasks]
                              ├─ SignalEngine   (ingestion → normalise → PRR → rank)
                              └─ ReadinessEngine (parse → catalog → map → score → gaps)
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Deterministic rule-based algorithms, no LLM | Regulatory outputs must be reproducible and auditable. The same input always produces the same output; there is no stochastic element. |
| rapidfuzz for fuzzy term matching | High-performance, Rust-backed fuzzy matching with a controllable similarity threshold. Used in both the event normalisation pipeline (≥ 0.90) and the CTD title mapper (≥ 0.85), replacing brittle string distance heuristics. |
| Versioned catalog with algorithm_version stamps | Every assessment and signal result records the catalog version and algorithm version that produced it. Regulatory results must be traceable to the exact algorithm state. |
| FastAPI BackgroundTasks (in-process) | Zero additional infrastructure for a prototype — no Redis, no Celery, no message queue. The job lifecycle (queued → running → complete/failed) is fully implemented and visible to the frontend via polling. |
| SQLite with SQLModel | Self-contained, zero-configuration, no server process. Appropriate for a prototype that runs locally with a single analyst. |
| TypeScript schemas mirror Python schemas exactly | `src/frontend/src/types/api.ts` is kept in sync with `src/backend/app/schemas.py` via the data contracts document. This prevents client/server type drift without a code-generation step. |
| No authentication layer | Explicitly scoped out for this prototype. All endpoints are public. The design is documented as a known limitation. |

---

## User Experience

1. The analyst opens the frontend at `http://localhost:5173` and creates a named project.
2. From the project detail page they select either the Signal Detection tab or the Readiness Assessment tab.
3. They drag-and-drop or browse for their data file and click Upload & Analyse.
4. A live progress indicator polls the job status. When the job completes, the results page renders automatically.
5. The analyst can filter, sort, and inspect results, then download a JSON or CSV export to share with colleagues or include in a regulatory package.

---

## IBM Technologies Used

- **IBM Bob:** Used as the primary AI-assisted development environment throughout the entire project. Bob navigated the multi-file codebase, maintained consistency between Python and TypeScript schemas, authored the test suite, and generated this documentation — all grounded in the actual implemented code rather than assumptions.
