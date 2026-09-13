"""Database initialisation, reset, and seed helpers.

Public API
----------
init_db(engine)        – create all tables (idempotent).
reset_db(engine)       – drop all tables then recreate them (test/dev only).
seed_ctd_catalog(session, catalog_version) – load the prototype CTD catalog.

Prototype CTD catalog disclaimer
---------------------------------
The catalog bundled here is a representative, illustrative structure covering
all five ICH CTD modules.  It is NOT a complete, jurisdiction-specific
regulatory checklist.  Requirements, section numbering, and guidance
references may differ across regions (FDA, EMA, PMDA, etc.) and drug types
(NME, biosimilar, generic, etc.).  Always consult the current applicable
guidance documents before use in a real regulatory submission.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, SQLModel, select

# Import all models so SQLModel.metadata is fully populated before any
# create_all / drop_all call.
import app.models  # noqa: F401  (side-effect import)
from app.models.readiness import CtdRequirement


# ---------------------------------------------------------------------------
# Catalog version constant
# ---------------------------------------------------------------------------

CTD_CATALOG_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Prototype CTD catalog seed data
#
# Structure: list of dicts matching the CtdRequirement ORM model fields.
# Covers all five CTD modules with representative mandatory and optional items.
# ---------------------------------------------------------------------------

_CTD_CATALOG: list[dict] = [
    # -----------------------------------------------------------------------
    # Module 1 – Administrative Information and Prescribing Information
    # -----------------------------------------------------------------------
    {
        "requirement_id": "CTD-1.2",
        "module": "1",
        "section": "1.2",
        "title": "Application Form",
        "description": (
            "Complete regulatory application form as required by the receiving "
            "authority (e.g. FDA Form 356h, EMA eCTD cover letter)."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.3.1",
        "module": "1",
        "section": "1.3.1",
        "title": "Proposed Labels and Labelling",
        "description": (
            "Draft prescribing information / SmPC / package insert including "
            "all required sections (indications, dosage, warnings, etc.)."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.3.2",
        "module": "1",
        "section": "1.3.2",
        "title": "Package Leaflet / Patient Information Leaflet",
        "description": (
            "Patient-facing information leaflet meeting applicable regional "
            "readability and content requirements."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4 Module 1",
    },
    {
        "requirement_id": "CTD-1.6",
        "module": "1",
        "section": "1.6",
        "title": "Environmental Risk Assessment (ERA)",
        "description": (
            "Environmental risk assessment where required by regional guidance "
            "(e.g. EMA CHMP ERA guideline)."
        ),
        "is_mandatory": False,
        "guidance_ref": "EMEA/CHMP/SWP/4447/00",
    },
    # -----------------------------------------------------------------------
    # Module 2 – Summaries
    # -----------------------------------------------------------------------
    {
        "requirement_id": "CTD-2.3",
        "module": "2",
        "section": "2.3",
        "title": "Quality Overall Summary (QOS)",
        "description": (
            "High-level written summary of the chemistry, manufacturing, and "
            "controls (CMC) information presented in Module 3."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4Q(R1)",
    },
    {
        "requirement_id": "CTD-2.4",
        "module": "2",
        "section": "2.4",
        "title": "Nonclinical Overview",
        "description": (
            "Integrated written overview of the nonclinical pharmacology, "
            "pharmacokinetics, and toxicology studies."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4S(R2)",
    },
    {
        "requirement_id": "CTD-2.5",
        "module": "2",
        "section": "2.5",
        "title": "Clinical Overview",
        "description": (
            "Critical analysis of the clinical data including benefit–risk "
            "assessment summarising Modules 4 and 5."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4E(R2)",
    },
    {
        "requirement_id": "CTD-2.7.4",
        "module": "2",
        "section": "2.7.4",
        "title": "Summary of Clinical Safety",
        "description": (
            "Tabulated and narrative summary of the safety profile from all "
            "clinical studies including adverse events and laboratory findings."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4E(R2) Section 2.7.4",
    },
    # -----------------------------------------------------------------------
    # Module 3 – Quality (Chemistry, Manufacturing, Controls)
    # -----------------------------------------------------------------------
    {
        "requirement_id": "CTD-3.2.S.1",
        "module": "3",
        "section": "3.2.S.1",
        "title": "Drug Substance — General Information",
        "description": (
            "Nomenclature, structural formula, molecular formula and weight, "
            "physicochemical properties, and general properties."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4Q(R1) S.1",
    },
    {
        "requirement_id": "CTD-3.2.S.2",
        "module": "3",
        "section": "3.2.S.2",
        "title": "Drug Substance — Manufacture",
        "description": (
            "Manufacturers, description of manufacturing process and process "
            "controls, controls of materials, controls of critical steps, "
            "process validation."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4Q(R1) S.2",
    },
    {
        "requirement_id": "CTD-3.2.S.3",
        "module": "3",
        "section": "3.2.S.3",
        "title": "Drug Substance — Characterisation",
        "description": (
            "Structure elucidation, analysis of potential impurities, and "
            "physicochemical characterisation data."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4Q(R1) S.3",
    },
    {
        "requirement_id": "CTD-3.2.P.1",
        "module": "3",
        "section": "3.2.P.1",
        "title": "Drug Product — Description and Composition",
        "description": (
            "Description of the dosage form and qualitative/quantitative "
            "composition of the drug product."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH M4Q(R1) P.1",
    },
    # -----------------------------------------------------------------------
    # Module 4 – Nonclinical Study Reports
    # -----------------------------------------------------------------------
    {
        "requirement_id": "CTD-4.2.1",
        "module": "4",
        "section": "4.2.1",
        "title": "Pharmacology — Primary Pharmacodynamics",
        "description": (
            "In vitro and in vivo studies characterising the mode of action "
            "and pharmacological effects relevant to the proposed indication."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH S7A",
    },
    {
        "requirement_id": "CTD-4.2.3",
        "module": "4",
        "section": "4.2.3",
        "title": "Toxicology — Single-Dose Toxicity",
        "description": (
            "Single-dose (acute) toxicity studies in at least two mammalian "
            "species by at least two routes of administration."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH S7A, M3(R2)",
    },
    {
        "requirement_id": "CTD-4.2.3.4",
        "module": "4",
        "section": "4.2.3.4",
        "title": "Toxicology — Genotoxicity",
        "description": (
            "Standard battery of genotoxicity tests (in vitro mutagenicity, "
            "chromosomal aberration, and in vivo assay) per ICH S2(R1)."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH S2(R1)",
    },
    # -----------------------------------------------------------------------
    # Module 5 – Clinical Study Reports
    # -----------------------------------------------------------------------
    {
        "requirement_id": "CTD-5.3.1",
        "module": "5",
        "section": "5.3.1",
        "title": "Bioavailability and Bioequivalence Studies",
        "description": (
            "Reports of studies establishing the bioavailability of the drug "
            "product and, where applicable, bioequivalence to the reference "
            "listed drug."
        ),
        "is_mandatory": True,
        "guidance_ref": "FDA 21 CFR 320; EMA Guideline on BA/BE",
    },
    {
        "requirement_id": "CTD-5.3.3",
        "module": "5",
        "section": "5.3.3",
        "title": "Efficacy and Safety — Controlled Clinical Studies",
        "description": (
            "Full clinical study reports for pivotal randomised controlled "
            "trials supporting the claimed indication(s)."
        ),
        "is_mandatory": True,
        "guidance_ref": "ICH E3, E6(R2), E9",
    },
    {
        "requirement_id": "CTD-5.3.5",
        "module": "5",
        "section": "5.3.5",
        "title": "Reports of Post-Marketing Experience",
        "description": (
            "Periodic safety update reports (PSURs/PBRERs) or periodic "
            "benefit–risk evaluation reports, if applicable, covering post-"
            "marketing safety experience."
        ),
        "is_mandatory": False,
        "guidance_ref": "ICH E2C(R2)",
    },
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def init_db(engine) -> None:
    """Create all tables defined in SQLModel.metadata (idempotent).

    Importing ``app.models`` at the top of this file guarantees every ORM
    class has been registered before this call.
    """
    SQLModel.metadata.create_all(engine)


def reset_db(engine) -> None:
    """Drop all tables then recreate them.

    Intended for test fixtures and development tooling only.
    Do NOT call this against a production database.
    """
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def seed_ctd_catalog(
    session: Session,
    catalog_version: str = CTD_CATALOG_VERSION,
    *,
    skip_if_exists: bool = True,
) -> list[CtdRequirement]:
    """Insert the prototype CTD catalog into the database.

    Parameters
    ----------
    session:
        An open SQLModel Session.
    catalog_version:
        Version string to stamp on every inserted row.
    skip_if_exists:
        When True (default), skip insertion if any rows with this
        catalog_version already exist.  Set to False to force re-seed.

    Returns
    -------
    List of CtdRequirement rows that were inserted (empty if skipped).

    Disclaimer
    ----------
    This prototype catalog is illustrative.  It is NOT a complete,
    jurisdiction-specific regulatory checklist.
    """
    if skip_if_exists:
        existing = session.exec(
            select(CtdRequirement).where(
                CtdRequirement.catalog_version == catalog_version
            )
        ).first()
        if existing is not None:
            return []

    inserted: list[CtdRequirement] = []
    for entry in _CTD_CATALOG:
        req = CtdRequirement(
            requirement_id=entry["requirement_id"],
            catalog_version=catalog_version,
            module=entry["module"],
            section=entry["section"],
            title=entry["title"],
            description=entry["description"],
            is_mandatory=entry["is_mandatory"],
            guidance_ref=entry.get("guidance_ref"),
        )
        session.add(req)
        inserted.append(req)

    session.commit()
    for req in inserted:
        session.refresh(req)

    return inserted
