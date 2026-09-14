# Problem Statement

## Background

New-drug approval requires pharmaceutical companies to submit a regulatory dossier to agencies such as the FDA, EMA, or PMDA. That process involves two distinct, high-stakes analytical tasks that run in parallel throughout development:

1. **Pharmacovigilance signal detection:** Continuously scanning accumulating adverse-event reports (from clinical trials, spontaneous reports, or databases such as FAERS) to identify disproportionate drug–event associations — statistical "signals" that may indicate a safety concern requiring label updates or regulatory action.

2. **Submission readiness assessment:** Auditing the draft dossier to confirm that every section required by the ICH Common Technical Document (CTD) standard is present, complete, and flagged for any gaps before submission.

---

## The Problem

### Signal Detection

Pharmacovigilance analysts responsible for signal detection currently face:

- **Volume:** A single quarterly FAERS data download contains hundreds of thousands of adverse-event records spanning thousands of drugs and event terms. Manual review is not feasible.
- **Inconsistency:** The same adverse event is reported under dozens of raw text variants ("liver injury", "hepatic failure", "hepatic damage"). Without normalisation, these are counted as unrelated events, fragmenting the statistical evidence and suppressing true signals.
- **Manual spreadsheet workflows:** Teams typically export data into Excel, manually pivot tables to count drug–event co-occurrences, and compute PRR values in formulas that are fragile, poorly versioned, and not reproducible.
- **Missing confidence intervals:** Without formal CI computation, analysts cannot distinguish a PRR of 3.0 based on 4 cases (highly uncertain) from one based on 80 cases.

A missed safety signal that reaches the market has direct patient harm consequences and severe regulatory liability.

### Submission Readiness

Regulatory affairs teams assembling a dossier face:

- **Checklist proliferation:** The ICH CTD structure spans five modules and dozens of mandatory sections. Each region (FDA, EMA, PMDA) may add jurisdiction-specific requirements. Tracking completeness across a large dossier in spreadsheets is error-prone and hard to audit.
- **Late discovery of gaps:** Section gaps are typically found during internal medical writing reviews or, worse, by agency reviewers. A Complete Response Letter (CRL) from the FDA due to a missing section can delay approval by 12–18 months and cost tens of millions of dollars.
- **No structured mapping:** There is no tool that takes a team's working dossier outline, matches it systematically against a regulatory requirements catalog, and produces a scored, prioritised gap list with specific recommendations.

---

## Who is Affected

- **Pharmacovigilance scientists and safety data analysts** at pharmaceutical companies and CROs responsible for periodic safety reviews, signal management, and aggregate report preparation.
- **Regulatory affairs specialists and medical writers** responsible for assembling and quality-checking the CTD dossier before submission.
- **Small-to-mid-size pharma teams** that cannot afford enterprise pharmacovigilance platforms (Oracle Argus, ArisGlobal) and currently rely entirely on spreadsheets and manual processes.

---

## Why It Matters

- A missed pharmacovigilance signal that leads to an approved drug with an undetected risk profile can cause patient harm and trigger post-market withdrawals (as seen with multiple historical cases).
- A CTD submission that is returned by regulators for missing sections costs 12–18 months of delay and, for a blockbuster drug, potentially hundreds of millions of dollars in lost revenue per year of delay.
- Both problems are solved today primarily with manual processes that do not scale and are not reproducible.

---

## Why Existing Solutions Fall Short

**Enterprise pharmacovigilance platforms** (Argus, ArisGlobal, Veeva Vault) are expensive, require months of implementation, and are inaccessible to smaller teams or academic researchers.

**Generic statistical tools** (R, SAS, Python scripts) can compute PRR but require each team to re-implement ingestion, deduplication, normalisation, CI computation, and result export from scratch — with no UI, no audit trail, and no integration with the submission workflow.

**Regulatory submission platforms** manage document assembly and version control but do not provide automated gap analysis against a CTD requirements catalog; that audit is done manually.

SafetyReady addresses both gaps in a single, self-contained tool that requires no cloud account, no API key, and no enterprise licence.
