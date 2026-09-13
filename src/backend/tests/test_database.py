"""Database persistence tests.

Covers:
  - Fresh initialisation (all tables created)
  - Reset behaviour (drop-and-recreate)
  - Seed loading (CTD catalog)
  - Foreign-key relationships for every domain
  - Index existence for required columns
  - Idempotent seed (skip_if_exists)
"""
import pytest
from sqlalchemy import inspect as sa_inspect, text
from sqlmodel import Session, SQLModel, create_engine, StaticPool, select

from app.db.init import (
    CTD_CATALOG_VERSION,
    init_db,
    reset_db,
    seed_ctd_catalog,
    _CTD_CATALOG,
)
from app.models import (
    # shared
    Project,
    ProjectStatus,
    Upload,
    UploadStatus,
    Job,
    JobType,
    JobStatus,
    AuditEvent,
    # signal
    Report,
    Drug,
    AdverseEvent,
    ReportDrug,
    ReportEvent,
    DrugEventPair,
    Signal,
    SignalSeverity,
    # readiness
    CtdRequirement,
    DossierSection,
    ReadinessAssessment,
    RequirementMapping,
    Gap,
    SectionStatus,
    ReviewStatus,
    GapSeverity,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def engine():
    eng = _make_engine()
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Helpers for creating minimal graph objects
# ---------------------------------------------------------------------------


def _project(session: Session, name: str = "Test Project") -> Project:
    p = Project(name=name)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _upload(session: Session, project: Project) -> Upload:
    u = Upload(
        project_id=project.id,
        filename="data.csv",
        content_type="text/csv",
        status=UploadStatus.complete,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _job(session: Session, project: Project, upload: Upload = None) -> Job:
    j = Job(
        project_id=project.id,
        upload_id=upload.id if upload else None,
        job_type=JobType.signal_detection,
        status=JobStatus.complete,
    )
    session.add(j)
    session.commit()
    session.refresh(j)
    return j


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    EXPECTED_TABLES = {
        "projects",
        "uploads",
        "jobs",
        "audit_events",
        "reports",
        "drugs",
        "adverse_events",
        "report_drugs",
        "report_events",
        "drug_event_pairs",
        "signals",
        "ctd_requirements",
        "dossier_sections",
        "readiness_assessments",
        "requirement_mappings",
        "gaps",
    }

    def test_all_tables_created(self, engine):
        inspector = sa_inspect(engine)
        tables = set(inspector.get_table_names())
        assert self.EXPECTED_TABLES == tables, (
            f"Missing tables: {self.EXPECTED_TABLES - tables}\n"
            f"Extra tables: {tables - self.EXPECTED_TABLES}"
        )

    def test_init_is_idempotent(self, engine):
        """Calling init_db a second time must not raise."""
        init_db(engine)
        inspector = sa_inspect(engine)
        tables = set(inspector.get_table_names())
        assert self.EXPECTED_TABLES == tables


# ---------------------------------------------------------------------------
# 2. Reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_drops_and_recreates(self, engine, session):
        # Insert a project to confirm data is present before reset
        p = _project(session, "BeforeReset")
        assert p.id is not None

        reset_db(engine)

        # Must be able to open a fresh session and find no rows
        with Session(engine) as new_session:
            projects = new_session.exec(select(Project)).all()
        assert projects == []

    def test_reset_recreates_all_tables(self, engine):
        reset_db(engine)
        inspector = sa_inspect(engine)
        tables = set(inspector.get_table_names())
        assert TestInit.EXPECTED_TABLES == tables

    def test_reset_then_insert(self, engine):
        reset_db(engine)
        with Session(engine) as s:
            p = _project(s, "AfterReset")
        assert p.id is not None


# ---------------------------------------------------------------------------
# 3. Seed — CTD catalog
# ---------------------------------------------------------------------------


class TestSeedCtdCatalog:
    def test_seed_inserts_all_entries(self, session):
        inserted = seed_ctd_catalog(session)
        assert len(inserted) == len(_CTD_CATALOG)

    def test_seed_all_modules_present(self, session):
        seed_ctd_catalog(session)
        rows = session.exec(select(CtdRequirement)).all()
        modules = {r.module for r in rows}
        assert modules == {"1", "2", "3", "4", "5"}

    def test_seed_catalog_version_stamped(self, session):
        seed_ctd_catalog(session, catalog_version="0.1.0")
        rows = session.exec(
            select(CtdRequirement).where(
                CtdRequirement.catalog_version == "0.1.0"
            )
        ).all()
        assert len(rows) == len(_CTD_CATALOG)

    def test_seed_idempotent_skip(self, session):
        """Second call with skip_if_exists=True must not duplicate rows."""
        seed_ctd_catalog(session)
        second = seed_ctd_catalog(session)
        assert second == []
        total = session.exec(select(CtdRequirement)).all()
        assert len(total) == len(_CTD_CATALOG)

    def test_seed_force_re_seed(self, session):
        """skip_if_exists=False must insert another batch (different version)."""
        seed_ctd_catalog(session, catalog_version="0.1.0")
        inserted = seed_ctd_catalog(
            session, catalog_version="0.2.0", skip_if_exists=False
        )
        assert len(inserted) == len(_CTD_CATALOG)
        total = session.exec(select(CtdRequirement)).all()
        assert len(total) == len(_CTD_CATALOG) * 2

    def test_seed_mandatory_and_optional_entries_present(self, session):
        seed_ctd_catalog(session)
        rows = session.exec(select(CtdRequirement)).all()
        mandatory = [r for r in rows if r.is_mandatory]
        optional = [r for r in rows if not r.is_mandatory]
        assert len(mandatory) > 0
        assert len(optional) > 0

    def test_seed_requirement_ids_unique(self, session):
        seed_ctd_catalog(session)
        rows = session.exec(
            select(CtdRequirement).where(
                CtdRequirement.catalog_version == CTD_CATALOG_VERSION
            )
        ).all()
        ids = [r.requirement_id for r in rows]
        assert len(ids) == len(set(ids)), "requirement_id values must be unique per catalog version"

    def test_seed_known_requirement_present(self, session):
        seed_ctd_catalog(session)
        row = session.exec(
            select(CtdRequirement).where(
                CtdRequirement.requirement_id == "CTD-3.2.S.1"
            )
        ).first()
        assert row is not None
        assert row.module == "3"
        assert row.is_mandatory is True

    def test_seed_guidance_refs_stored(self, session):
        seed_ctd_catalog(session)
        rows = session.exec(select(CtdRequirement)).all()
        rows_with_refs = [r for r in rows if r.guidance_ref is not None]
        assert len(rows_with_refs) > 0


# ---------------------------------------------------------------------------
# 4. Shared entity foreign-key relationships
# ---------------------------------------------------------------------------


class TestSharedEntityRelationships:
    def test_upload_links_to_project(self, session):
        p = _project(session)
        u = _upload(session, p)
        assert u.project_id == p.id
        fetched = session.get(Upload, u.id)
        assert fetched.project_id == p.id

    def test_job_links_to_project_and_upload(self, session):
        p = _project(session)
        u = _upload(session, p)
        j = _job(session, p, u)
        assert j.project_id == p.id
        assert j.upload_id == u.id

    def test_job_without_upload(self, session):
        p = _project(session)
        j = _job(session, p)
        assert j.upload_id is None

    def test_audit_event_links_to_project_and_job(self, session):
        p = _project(session)
        u = _upload(session, p)
        j = _job(session, p, u)
        ae = AuditEvent(
            project_id=p.id,
            job_id=j.id,
            event_type="job.completed",
            actor="system",
            detail_json='{"result": "ok"}',
        )
        session.add(ae)
        session.commit()
        session.refresh(ae)
        assert ae.id is not None
        assert ae.project_id == p.id
        assert ae.job_id == j.id

    def test_audit_event_without_project(self, session):
        ae = AuditEvent(event_type="system.startup")
        session.add(ae)
        session.commit()
        session.refresh(ae)
        assert ae.project_id is None

    def test_job_status_index_queryable(self, session):
        p = _project(session)
        j = _job(session, p)
        rows = session.exec(
            select(Job).where(Job.status == JobStatus.complete)
        ).all()
        assert any(r.id == j.id for r in rows)


# ---------------------------------------------------------------------------
# 5. Signal domain foreign-key relationships
# ---------------------------------------------------------------------------


class TestSignalEntityRelationships:
    def _setup_base(self, session):
        p = _project(session)
        u = _upload(session, p)
        j = _job(session, p, u)
        return p, u, j

    def test_report_links_to_project_and_upload(self, session):
        p, u, j = self._setup_base(session)
        rpt = Report(
            project_id=p.id,
            upload_id=u.id,
            primaryid="PID001",
            case_id="C001",
            case_version="1",
        )
        session.add(rpt)
        session.commit()
        session.refresh(rpt)
        assert rpt.id is not None
        assert rpt.project_id == p.id
        assert rpt.upload_id == u.id

    def test_drug_links_to_project(self, session):
        p, u, j = self._setup_base(session)
        d = Drug(
            project_id=p.id,
            drug_id="DRUGALPHA",
            name="DRUGALPHA",
            raw_name="drugalpha",
        )
        session.add(d)
        session.commit()
        session.refresh(d)
        assert d.project_id == p.id

    def test_adverse_event_links_to_project(self, session):
        p, u, j = self._setup_base(session)
        ae = AdverseEvent(
            project_id=p.id,
            event_id="hepatic_disorder",
            preferred_term="Hepatic Disorder",
            raw_term="liver injury",
            normalisation_method="alias_lookup",
            normalisation_confidence=0.95,
        )
        session.add(ae)
        session.commit()
        session.refresh(ae)
        assert ae.project_id == p.id

    def test_report_drug_links_report_and_drug(self, session):
        p, u, j = self._setup_base(session)
        rpt = Report(
            project_id=p.id, upload_id=u.id,
            primaryid="PID002", case_id="C002", case_version="1",
        )
        session.add(rpt)
        session.commit()
        session.refresh(rpt)

        d = Drug(
            project_id=p.id, drug_id="DRUGBETA",
            name="DRUGBETA", raw_name="drugbeta",
        )
        session.add(d)
        session.commit()
        session.refresh(d)

        rd = ReportDrug(report_id=rpt.id, drug_id=d.id, raw_name="drugbeta")
        session.add(rd)
        session.commit()
        session.refresh(rd)
        assert rd.report_id == rpt.id
        assert rd.drug_id == d.id

    def test_report_event_links_report_and_event(self, session):
        p, u, j = self._setup_base(session)
        rpt = Report(
            project_id=p.id, upload_id=u.id,
            primaryid="PID003", case_id="C003", case_version="1",
        )
        session.add(rpt)
        session.commit()
        session.refresh(rpt)

        ae = AdverseEvent(
            project_id=p.id, event_id="headache",
            preferred_term="Headache", raw_term="headache",
        )
        session.add(ae)
        session.commit()
        session.refresh(ae)

        re_ = ReportEvent(report_id=rpt.id, event_id=ae.id, raw_term="headache")
        session.add(re_)
        session.commit()
        session.refresh(re_)
        assert re_.report_id == rpt.id
        assert re_.event_id == ae.id

    def test_drug_event_pair_links_job_drug_event(self, session):
        p, u, j = self._setup_base(session)
        d = Drug(
            project_id=p.id, drug_id="DRUGALPHA",
            name="DRUGALPHA", raw_name="DRUGALPHA",
        )
        ae = AdverseEvent(
            project_id=p.id, event_id="hepatic_disorder",
            preferred_term="Hepatic Disorder", raw_term="liver injury",
        )
        session.add(d)
        session.add(ae)
        session.commit()
        session.refresh(d)
        session.refresh(ae)

        pair = DrugEventPair(
            job_id=j.id, drug_id=d.id, event_id=ae.id,
            a=34, b=16, c=6, d=61, prr=8.5,
            prr_lower_ci=5.1, prr_upper_ci=14.2,
        )
        session.add(pair)
        session.commit()
        session.refresh(pair)
        assert pair.job_id == j.id
        assert pair.drug_id == d.id
        assert pair.event_id == ae.id
        assert pair.prr == pytest.approx(8.5)

    def test_signal_links_project_job_and_pair(self, session):
        p, u, j = self._setup_base(session)
        d = Drug(
            project_id=p.id, drug_id="DRUGALPHA",
            name="DRUGALPHA", raw_name="DRUGALPHA",
        )
        ae = AdverseEvent(
            project_id=p.id, event_id="hepatic_disorder",
            preferred_term="Hepatic Disorder", raw_term="liver injury",
        )
        session.add(d)
        session.add(ae)
        session.commit()
        session.refresh(d)
        session.refresh(ae)

        pair = DrugEventPair(
            job_id=j.id, drug_id=d.id, event_id=ae.id,
            a=34, b=16, c=6, d=61, prr=8.5,
        )
        session.add(pair)
        session.commit()
        session.refresh(pair)

        sig = Signal(
            project_id=p.id,
            job_id=j.id,
            drug_event_pair_id=pair.id,
            title="DRUGALPHA — Hepatic Disorder",
            description="PRR=8.5, above threshold.",
            severity=SignalSeverity.critical,
            algorithm_version="0.1.0",
        )
        session.add(sig)
        session.commit()
        session.refresh(sig)
        assert sig.id is not None
        assert sig.drug_event_pair_id == pair.id


# ---------------------------------------------------------------------------
# 6. Readiness domain foreign-key relationships
# ---------------------------------------------------------------------------


class TestReadinessEntityRelationships:
    def _setup(self, session):
        p = _project(session)
        u = _upload(session, p)
        j = _job(session, p, u)
        j.job_type = JobType.readiness_assessment
        session.add(j)
        session.commit()
        session.refresh(j)
        return p, u, j

    def test_readiness_assessment_links_project_job(self, session):
        p, u, j = self._setup(session)
        ra = ReadinessAssessment(
            project_id=p.id,
            job_id=j.id,
            upload_id=u.id,
            overall_score=0.72,
            summary="Good readiness.",
            algorithm_version="0.1.0",
            catalog_version=CTD_CATALOG_VERSION,
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)
        assert ra.id is not None
        assert ra.project_id == p.id
        assert ra.job_id == j.id

    def test_dossier_section_links_assessment(self, session):
        p, u, j = self._setup(session)
        ra = ReadinessAssessment(
            project_id=p.id, job_id=j.id,
            overall_score=0.5, summary="Moderate.",
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        ds = DossierSection(
            project_id=p.id,
            upload_id=u.id,
            assessment_id=ra.id,
            section_id="SEC-3.2.S.1",
            module="3",
            title="Drug Substance General Info",
            status=SectionStatus.complete,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)
        assert ds.assessment_id == ra.id

    def test_requirement_mapping_links_assessment(self, session):
        p, u, j = self._setup(session)
        ra = ReadinessAssessment(
            project_id=p.id, job_id=j.id,
            overall_score=0.6, summary="Moderate.",
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        rm = RequirementMapping(
            assessment_id=ra.id,
            requirement_id="CTD-3.2.S.1",
            status=SectionStatus.complete,
        )
        session.add(rm)
        session.commit()
        session.refresh(rm)
        assert rm.assessment_id == ra.id
        assert rm.requirement_id == "CTD-3.2.S.1"
        assert rm.dossier_section_id is None

    def test_gap_links_assessment(self, session):
        p, u, j = self._setup(session)
        ra = ReadinessAssessment(
            project_id=p.id, job_id=j.id,
            overall_score=0.4, summary="Low.",
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        gap = Gap(
            assessment_id=ra.id,
            gap_id="GAP-001",
            requirement_id="CTD-1.3.2",
            description="Package Leaflet missing.",
            severity=GapSeverity.high,
            recommendation="Prepare and submit Package Leaflet.",
        )
        session.add(gap)
        session.commit()
        session.refresh(gap)
        assert gap.id is not None
        assert gap.assessment_id == ra.id
        assert gap.review_status == ReviewStatus.not_started

    def test_gap_with_dossier_section(self, session):
        p, u, j = self._setup(session)
        ra = ReadinessAssessment(
            project_id=p.id, job_id=j.id,
            overall_score=0.8, summary="High.",
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        ds = DossierSection(
            project_id=p.id, upload_id=u.id, assessment_id=ra.id,
            section_id="SEC-1.3.2", module="1",
            title="Package Leaflet", status=SectionStatus.missing,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        gap = Gap(
            assessment_id=ra.id,
            gap_id="GAP-002",
            requirement_id="CTD-1.3.2",
            dossier_section_id=ds.id,
            description="Section present but empty.",
            severity=GapSeverity.medium,
            recommendation="Complete the package leaflet.",
        )
        session.add(gap)
        session.commit()
        session.refresh(gap)
        assert gap.dossier_section_id == ds.id

    def test_full_assessment_query(self, session):
        """Query gaps and mappings for a given assessment via assessment_id."""
        p, u, j = self._setup(session)
        seed_ctd_catalog(session)

        ra = ReadinessAssessment(
            project_id=p.id, job_id=j.id,
            overall_score=0.55, summary="Needs work.",
        )
        session.add(ra)
        session.commit()
        session.refresh(ra)

        # Add two mappings
        for req_id, status in [
            ("CTD-3.2.S.1", SectionStatus.complete),
            ("CTD-3.2.S.3", SectionStatus.missing),
        ]:
            session.add(RequirementMapping(
                assessment_id=ra.id,
                requirement_id=req_id,
                status=status,
            ))
        # Add one gap
        session.add(Gap(
            assessment_id=ra.id,
            gap_id="GAP-001",
            requirement_id="CTD-3.2.S.3",
            description="Characterisation missing.",
            severity=GapSeverity.high,
            recommendation="Include structure elucidation.",
        ))
        session.commit()

        mappings = session.exec(
            select(RequirementMapping).where(
                RequirementMapping.assessment_id == ra.id
            )
        ).all()
        gaps = session.exec(
            select(Gap).where(Gap.assessment_id == ra.id)
        ).all()
        assert len(mappings) == 2
        assert len(gaps) == 1
        assert gaps[0].requirement_id == "CTD-3.2.S.3"


# ---------------------------------------------------------------------------
# 7. Index existence
# ---------------------------------------------------------------------------


class TestIndexes:
    """Verify that indexes declared in the models are actually created."""

    EXPECTED_INDEXES = {
        "uploads": ["ix_uploads_project_id"],
        "jobs": ["ix_jobs_project_id", "ix_jobs_status"],
        "audit_events": ["ix_audit_events_project_id"],
        "reports": ["ix_reports_project_id", "ix_reports_case_id", "ix_reports_upload_id"],
        "drugs": ["ix_drugs_project_id", "ix_drugs_drug_id"],
        "adverse_events": ["ix_adverse_events_project_id", "ix_adverse_events_event_id"],
        "report_drugs": ["ix_report_drugs_report_id", "ix_report_drugs_drug_id"],
        "report_events": ["ix_report_events_report_id", "ix_report_events_event_id"],
        "drug_event_pairs": [
            "ix_drug_event_pairs_job_id",
            "ix_drug_event_pairs_drug_id",
            "ix_drug_event_pairs_event_id",
        ],
        "signals": ["ix_signals_project_id", "ix_signals_job_id"],
        "ctd_requirements": [
            "ix_ctd_requirements_requirement_id",
            "ix_ctd_requirements_catalog_version",
        ],
        "dossier_sections": [
            "ix_dossier_sections_project_id",
            "ix_dossier_sections_upload_id",
            "ix_dossier_sections_assessment_id",
        ],
        "requirement_mappings": [
            "ix_requirement_mappings_assessment_id",
            "ix_requirement_mappings_requirement_id",
        ],
        "gaps": ["ix_gaps_assessment_id", "ix_gaps_requirement_id"],
    }

    def test_indexes_created(self, engine):
        inspector = sa_inspect(engine)
        for table, expected_idx_names in self.EXPECTED_INDEXES.items():
            actual_names = {
                idx["name"] for idx in inspector.get_indexes(table)
            }
            for idx_name in expected_idx_names:
                assert idx_name in actual_names, (
                    f"Index '{idx_name}' missing from table '{table}'. "
                    f"Found: {actual_names}"
                )
