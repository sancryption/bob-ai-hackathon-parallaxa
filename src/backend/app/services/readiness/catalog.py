"""CTD requirements catalog for the Readiness Assessment engine.

The catalog is the authoritative source of:
  - requirement_id, module, section_code, title, expected_content
  - requiredness (mandatory / optional / conditional)
  - applicability_rule
  - keywords (for keyword/title matching)
  - weight (scoring weight, default 1.0)
  - catalog_version

The catalog covers all five ICH CTD modules and is versioned so that
assessments record exactly which catalog version produced their scores.

Disclaimer
----------
This prototype catalog is illustrative and representative.  It is NOT a
complete, jurisdiction-specific regulatory checklist.  Requirements,
section numbering, and guidance references may differ across regions
(FDA, EMA, PMDA, etc.) and drug types.  Always consult the current
applicable guidance documents before use in a real regulatory submission.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.services.readiness.types import RequirementRecord

CATALOG_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Master catalog list
# ---------------------------------------------------------------------------

_CATALOG_DATA: List[Dict] = [
    # =======================================================================
    # Module 1 – Administrative Information and Prescribing Information
    # =======================================================================
    {
        "requirement_id": "CTD-1.2",
        "module": "1",
        "section_code": "1.2",
        "title": "Application Form",
        "expected_content": (
            "Completed regulatory application form as required by the receiving "
            "authority (e.g. FDA Form 356h, EMA eCTD cover letter)."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": ["application", "form", "submission", "cover letter", "356h"],
        "weight": 1.0,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.3.1",
        "module": "1",
        "section_code": "1.3.1",
        "title": "Proposed Labels and Labelling / SmPC",
        "expected_content": (
            "Draft prescribing information / Summary of Product Characteristics (SmPC) / "
            "package insert including all required sections (indications, dosage, warnings)."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "label", "labelling", "smpc", "prescribing information",
            "package insert", "spc", "summary of product characteristics",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.3.2",
        "module": "1",
        "section_code": "1.3.2",
        "title": "Package Leaflet / Patient Information Leaflet",
        "expected_content": (
            "Patient-facing information leaflet meeting applicable regional readability "
            "and content requirements."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "package leaflet", "patient information", "leaflet", "pil",
            "patient leaflet", "consumer information",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.6",
        "module": "1",
        "section_code": "1.6",
        "title": "Environmental Risk Assessment (ERA)",
        "expected_content": (
            "Environmental risk assessment where required by regional guidance."
        ),
        "requiredness": "optional",
        "applicability_rule": "if_required_by_region",
        "keywords": ["environmental", "era", "environmental risk", "ecotoxicology"],
        "weight": 0.5,
        "guidance_ref": "EMEA/CHMP/SWP/4447/00",
    },
    # =======================================================================
    # Module 2 – Summaries
    # =======================================================================
    {
        "requirement_id": "CTD-2.3",
        "module": "2",
        "section_code": "2.3",
        "title": "Quality Overall Summary (QOS)",
        "expected_content": (
            "High-level written summary of chemistry, manufacturing, and controls (CMC) "
            "information presented in Module 3."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": ["quality overall summary", "qos", "cmc summary", "quality summary"],
        "weight": 1.0,
        "guidance_ref": "ICH M4Q(R1)",
    },
    {
        "requirement_id": "CTD-2.4",
        "module": "2",
        "section_code": "2.4",
        "title": "Nonclinical Overview",
        "expected_content": (
            "Integrated written overview of the nonclinical pharmacology, "
            "pharmacokinetics, and toxicology studies."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "nonclinical overview", "non-clinical overview",
            "preclinical overview", "nonclinical",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4S(R2)",
    },
    {
        "requirement_id": "CTD-2.5",
        "module": "2",
        "section_code": "2.5",
        "title": "Clinical Overview",
        "expected_content": (
            "Critical analysis of the clinical data including benefit-risk assessment "
            "summarising Modules 4 and 5."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "clinical overview", "benefit-risk", "benefit risk",
            "clinical summary overview",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4E(R2)",
    },
    {
        "requirement_id": "CTD-2.6",
        "module": "2",
        "section_code": "2.6",
        "title": "Nonclinical Written and Tabulated Summaries",
        "expected_content": (
            "Written summaries and tabulated data for nonclinical pharmacology, "
            "pharmacokinetics, and toxicology studies."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "nonclinical written", "nonclinical tabulated", "nonclinical summaries",
            "preclinical summaries", "tabulated summaries",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4S(R2)",
    },
    {
        "requirement_id": "CTD-2.7",
        "module": "2",
        "section_code": "2.7",
        "title": "Clinical Summary",
        "expected_content": (
            "Tabulated and written clinical study summaries."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "clinical summary", "clinical study summary", "tabulated clinical",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4E(R2)",
    },
    # =======================================================================
    # Module 3 – Quality (Chemistry, Manufacturing, Controls)
    # =======================================================================
    {
        "requirement_id": "CTD-3.2.S.1",
        "module": "3",
        "section_code": "3.2.S.1",
        "title": "Drug Substance — General Information",
        "expected_content": (
            "Nomenclature, structural formula, molecular formula and weight, "
            "physicochemical properties, and general properties."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "drug substance", "general information", "nomenclature",
            "structure", "physicochemical", "molecular formula",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4Q(R1) S.1",
    },
    {
        "requirement_id": "CTD-3.2.S.2",
        "module": "3",
        "section_code": "3.2.S.2",
        "title": "Drug Substance — Manufacture",
        "expected_content": (
            "Manufacturers, description of manufacturing process and process controls, "
            "controls of materials, critical steps, process validation."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "drug substance manufacture", "manufacturing process", "process controls",
            "process validation", "manufacturer",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4Q(R1) S.2",
    },
    {
        "requirement_id": "CTD-3.2.S.3",
        "module": "3",
        "section_code": "3.2.S.3",
        "title": "Drug Substance — Characterisation",
        "expected_content": (
            "Structure elucidation, analysis of potential impurities, "
            "and physicochemical characterisation data."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "characterisation", "characterization", "structure elucidation",
            "impurities", "drug substance characteris",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4Q(R1) S.3",
    },
    {
        "requirement_id": "CTD-3.2.P.1",
        "module": "3",
        "section_code": "3.2.P.1",
        "title": "Drug Product — Description and Composition",
        "expected_content": (
            "Description of the dosage form and qualitative/quantitative "
            "composition of the drug product."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "drug product", "description", "composition", "dosage form",
            "formulation", "quantitative composition",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH M4Q(R1) P.1",
    },
    {
        "requirement_id": "CTD-3.2.P.2",
        "module": "3",
        "section_code": "3.2.P.2",
        "title": "Drug Product — Pharmaceutical Development",
        "expected_content": (
            "Formulation development history and rationale."
        ),
        "requiredness": "optional",
        "applicability_rule": "if_available",
        "keywords": [
            "pharmaceutical development", "formulation development",
            "development history", "drug product development",
        ],
        "weight": 0.5,
        "guidance_ref": "ICH M4Q(R1) P.2",
    },
    # =======================================================================
    # Module 4 – Nonclinical Study Reports
    # =======================================================================
    {
        "requirement_id": "CTD-4.2.1",
        "module": "4",
        "section_code": "4.2.1",
        "title": "Pharmacology — Primary Pharmacodynamics",
        "expected_content": (
            "In vitro and in vivo studies characterising the mode of action "
            "and pharmacological effects relevant to the proposed indication."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "primary pharmacodynamics", "pharmacology", "mechanism of action",
            "pharmacodynamics", "in vitro", "in vivo",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH S7A",
    },
    {
        "requirement_id": "CTD-4.2.2",
        "module": "4",
        "section_code": "4.2.2",
        "title": "Pharmacology — Safety Pharmacology",
        "expected_content": (
            "Core battery safety pharmacology studies (CNS, CV, respiratory)."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "safety pharmacology", "herg", "cardiovascular", "cns", "respiratory",
            "core battery",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH S7A",
    },
    {
        "requirement_id": "CTD-4.2.3",
        "module": "4",
        "section_code": "4.2.3",
        "title": "Pharmacology — Secondary Pharmacodynamics",
        "expected_content": (
            "Off-target binding and secondary pharmacodynamic effects."
        ),
        "requiredness": "optional",
        "applicability_rule": "if_available",
        "keywords": [
            "secondary pharmacodynamics", "off-target", "secondary pharmacology",
        ],
        "weight": 0.5,
        "guidance_ref": "ICH S7A",
    },
    # =======================================================================
    # Module 5 – Clinical Study Reports
    # =======================================================================
    {
        "requirement_id": "CTD-5.3.1",
        "module": "5",
        "section_code": "5.3.1",
        "title": "Bioavailability / Bioequivalence Studies",
        "expected_content": (
            "Reports of studies establishing the bioavailability of the drug product "
            "and, where applicable, bioequivalence to the reference listed drug."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "bioavailability", "bioequivalence", "ba", "be", "biopharmaceutics",
            "pharmacokinetics studies",
        ],
        "weight": 1.0,
        "guidance_ref": "FDA 21 CFR 320; EMA Guideline on BA/BE",
    },
    {
        "requirement_id": "CTD-5.3.3",
        "module": "5",
        "section_code": "5.3.3",
        "title": "Efficacy and Safety — Controlled Clinical Studies",
        "expected_content": (
            "Full clinical study reports for pivotal randomised controlled trials "
            "supporting the claimed indication(s)."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "controlled clinical studies", "efficacy", "safety studies",
            "clinical trial", "pivotal", "randomised", "rct",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH E3, E6(R2), E9",
    },
    {
        "requirement_id": "CTD-5.3.5",
        "module": "5",
        "section_code": "5.3.5",
        "title": "Reports of Efficacy and Safety Studies",
        "expected_content": (
            "Full clinical study reports for efficacy and safety studies."
        ),
        "requiredness": "mandatory",
        "applicability_rule": "always",
        "keywords": [
            "efficacy and safety", "safety study reports", "clinical reports",
            "study reports", "phase ii", "phase iii",
        ],
        "weight": 1.0,
        "guidance_ref": "ICH E3",
    },
    {
        "requirement_id": "CTD-5.3.6",
        "module": "5",
        "section_code": "5.3.6",
        "title": "Post-Marketing Experience / PSUR",
        "expected_content": (
            "Periodic safety update reports (PSURs/PBRERs) or periodic "
            "benefit-risk evaluation reports."
        ),
        "requiredness": "optional",
        "applicability_rule": "if_post_marketing_data_available",
        "keywords": [
            "psur", "pbrer", "post-marketing", "post marketing",
            "periodic safety", "spontaneous reports",
        ],
        "weight": 0.5,
        "guidance_ref": "ICH E2C(R2)",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_catalog(
    catalog_version: str = CATALOG_VERSION,
) -> List[RequirementRecord]:
    """Return the full requirements catalog as a list of RequirementRecord."""
    return [
        RequirementRecord(
            requirement_id=d["requirement_id"],
            module=d["module"],
            section_code=d["section_code"],
            title=d["title"],
            expected_content=d["expected_content"],
            requiredness=d["requiredness"],
            applicability_rule=d["applicability_rule"],
            keywords=d["keywords"],
            weight=d["weight"],
            catalog_version=catalog_version,
            guidance_ref=d.get("guidance_ref"),
        )
        for d in _CATALOG_DATA
    ]


def get_catalog_by_id(
    catalog_version: str = CATALOG_VERSION,
) -> Dict[str, RequirementRecord]:
    """Return the catalog indexed by requirement_id."""
    return {r.requirement_id: r for r in build_catalog(catalog_version)}


def get_catalog_by_section(
    catalog_version: str = CATALOG_VERSION,
) -> Dict[str, RequirementRecord]:
    """Return the catalog indexed by normalised section_code."""
    return {r.section_code: r for r in build_catalog(catalog_version)}
