"""Schema contract tests.

These tests exercise every Pydantic model defined in app/schemas.py
with both valid and invalid data, verifying:
  - all 14 contract types round-trip correctly;
  - field constraints are enforced (ge/le, min_length, enums);
  - optional fields default correctly;
  - the fixture files parse against their schemas.
"""
import json
import csv
import pathlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
    # Envelopes
    ValidationDetail,
    ErrorDetail,
    ErrorEnvelope,
    OkEnvelope,
    # Project
    ProjectStatus,
    ProjectCreate,
    ProjectRead,
    ProjectList,
    # Upload
    UploadStatus,
    UploadRead,
    # Job
    JobType,
    JobStatus,
    JobProgress,
    JobRead,
    # Event / normalisation
    NormalizationProvenance,
    EventCluster,
    # Signal
    SignalSeverity,
    ThresholdStatus,
    SignalSummary,
    SignalResult,
    SignalRead,
    SignalList,
    SignalSummaryList,
    # CTD / Dossier
    CtdModule,
    SectionStatus,
    CtdRequirement,
    DossierSection,
    RequirementMapping,
    # Readiness
    ReviewStatus,
    ModuleScore,
    GapSeverity,
    GapResult,
    GapList,
    ReadinessAssessmentRead,
    # Legacy
    GapRead,
    RequirementRead,
    RequirementList,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return NOW.isoformat()


# ---------------------------------------------------------------------------
# 1. ErrorEnvelope / ValidationDetail
# ---------------------------------------------------------------------------

class TestErrorEnvelope:
    def test_basic(self):
        e = ErrorEnvelope(error=ErrorDetail(code="ERR", message="oops"))
        assert e.error.code == "ERR"
        assert e.error.field is None
        assert e.error.validation_errors is None

    def test_with_validation_details(self):
        vd = ValidationDetail(loc=["body", "name"], msg="too short", type="string_too_short")
        e = ErrorEnvelope(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request body invalid",
                validation_errors=[vd],
            )
        )
        assert len(e.error.validation_errors) == 1
        assert e.error.validation_errors[0].loc == ["body", "name"]

    def test_ok_envelope_generic(self):
        env = OkEnvelope(data={"key": "value"})
        assert env.data["key"] == "value"


# ---------------------------------------------------------------------------
# 2. Project
# ---------------------------------------------------------------------------

class TestProject:
    def test_create_valid(self):
        p = ProjectCreate(name="Test", description="desc")
        assert p.name == "Test"

    def test_create_name_too_short(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="")

    def test_read_round_trip(self):
        p = ProjectRead(
            id=1, name="P", description=None,
            status=ProjectStatus.draft,
            created_at=NOW, updated_at=NOW,
        )
        assert p.status == ProjectStatus.draft

    def test_project_list(self):
        item = ProjectRead(id=1, name="P", description=None,
                           status="ready", created_at=NOW, updated_at=NOW)
        pl = ProjectList(items=[item], total=1)
        assert pl.total == 1


# ---------------------------------------------------------------------------
# 3. Upload
# ---------------------------------------------------------------------------

class TestUpload:
    def test_upload_read_optional_metadata(self):
        u = UploadRead(
            id=1, project_id=1, filename="data.csv",
            content_type="text/csv", status=UploadStatus.complete,
            created_at=NOW,
        )
        assert u.row_count is None
        assert u.duplicate_count is None
        assert u.size_bytes is None

    def test_upload_read_with_metadata(self):
        u = UploadRead(
            id=2, project_id=1, filename="data.csv",
            content_type="text/csv", status=UploadStatus.complete,
            created_at=NOW, size_bytes=20480, row_count=117, duplicate_count=1,
        )
        assert u.row_count == 117
        assert u.duplicate_count == 1

    def test_upload_invalid_status(self):
        with pytest.raises(ValidationError):
            UploadRead(
                id=1, project_id=1, filename="x", content_type="x",
                status="unknown_status", created_at=NOW,
            )


# ---------------------------------------------------------------------------
# 4. Job + JobProgress
# ---------------------------------------------------------------------------

class TestJob:
    def test_job_progress(self):
        p = JobProgress(percent=55.0, message="Running PRR", step="compute_prr")
        assert p.percent == 55.0

    def test_job_progress_out_of_range(self):
        with pytest.raises(ValidationError):
            JobProgress(percent=101.0, message="x", step="x")

    def test_job_read_with_progress(self):
        j = JobRead(
            id=1, project_id=1,
            job_type=JobType.signal_detection,
            status=JobStatus.running,
            progress=JobProgress(percent=50.0, message="halfway", step="prr"),
            created_at=NOW, updated_at=NOW,
        )
        assert j.progress.percent == 50.0

    def test_job_read_without_progress(self):
        j = JobRead(
            id=2, project_id=1,
            job_type=JobType.readiness_assessment,
            status=JobStatus.complete,
            created_at=NOW, updated_at=NOW,
        )
        assert j.progress is None


# ---------------------------------------------------------------------------
# 5. NormalizationProvenance + EventCluster
# ---------------------------------------------------------------------------

class TestEventCluster:
    def test_provenance(self):
        p = NormalizationProvenance(
            raw_term="severe headache",
            preferred_term="Headache",
            meddra_code="10019211",
            method="alias_lookup",
            confidence=0.95,
        )
        assert p.confidence == 0.95

    def test_provenance_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            NormalizationProvenance(
                raw_term="x", preferred_term="y", method="exact", confidence=1.1
            )

    def test_event_cluster(self):
        prov = NormalizationProvenance(
            raw_term="headache", preferred_term="Headache",
            method="exact_match", confidence=1.0,
        )
        ec = EventCluster(
            preferred_term="Headache",
            raw_aliases=["headache", "severe headache"],
            meddra_code="10019211",
            case_count=33,
            provenances=[prov],
        )
        assert len(ec.raw_aliases) == 2
        assert ec.case_count == 33


# ---------------------------------------------------------------------------
# 6. SignalSummary + SignalResult + SignalRead
# ---------------------------------------------------------------------------

class TestSignal:
    def _make_result(self, **kwargs):
        defaults = dict(
            drug="DRUGALPHA", event="Hepatic disorder",
            a=34, b=16, c=6, d=61,
            prr=8.5, prr_lower_ci=5.1, prr_upper_ci=14.2,
            threshold_status=ThresholdStatus.above,
            severity=SignalSeverity.critical,
            rank=1,
            algorithm_version="0.1.0",
            disclaimer="For investigational use only.",
        )
        defaults.update(kwargs)
        return SignalResult(**defaults)

    def test_signal_result_valid(self):
        r = self._make_result()
        assert r.prr == 8.5
        assert r.rank == 1
        assert r.threshold_status == ThresholdStatus.above

    def test_signal_result_negative_a(self):
        with pytest.raises(ValidationError):
            self._make_result(a=-1)

    def test_signal_result_prr_negative(self):
        with pytest.raises(ValidationError):
            self._make_result(prr=-0.1)

    def test_signal_result_rank_zero(self):
        with pytest.raises(ValidationError):
            self._make_result(rank=0)

    def test_signal_summary(self):
        s = SignalSummary(
            drug="DRUGALPHA", event="Hepatic disorder",
            prr=8.5, severity=SignalSeverity.critical,
            threshold_status=ThresholdStatus.above,
            rank=1, total_cases=34,
        )
        assert s.total_cases == 34

    def test_signal_read_with_result(self):
        r = self._make_result()
        sr = SignalRead(
            id=1, project_id=1, job_id=1,
            title="DRUGALPHA — Hepatic disorder",
            description="PRR=8.5, above threshold",
            severity=SignalSeverity.critical,
            result=r, created_at=NOW,
        )
        assert sr.result.prr == 8.5

    def test_signal_list(self):
        sl = SignalList(items=[], total=0)
        assert sl.total == 0

    def test_signal_summary_list(self):
        ssl = SignalSummaryList(items=[], total=0)
        assert ssl.total == 0


# ---------------------------------------------------------------------------
# 7. CTD / Dossier types
# ---------------------------------------------------------------------------

class TestDossier:
    def test_ctd_requirement(self):
        r = CtdRequirement(
            requirement_id="CTD-3.2.S.1",
            module=CtdModule.m3,
            section="3.2.S.1",
            title="Drug Substance Info",
            description="Nomenclature and structure.",
            is_mandatory=True,
        )
        assert r.module == CtdModule.m3
        assert r.is_mandatory is True

    def test_dossier_section_all_statuses(self):
        for st in SectionStatus:
            ds = DossierSection(
                section_id=f"S-{st.value}",
                module=CtdModule.m1,
                title=f"Section {st}",
                status=st,
            )
            assert ds.status == st

    def test_requirement_mapping_no_section(self):
        m = RequirementMapping(
            requirement_id="CTD-1.3.2",
            status=SectionStatus.missing,
        )
        assert m.dossier_section_id is None

    def test_requirement_mapping_with_section(self):
        m = RequirementMapping(
            requirement_id="CTD-1.2",
            dossier_section_id="SEC-1.2",
            status=SectionStatus.complete,
        )
        assert m.dossier_section_id == "SEC-1.2"


# ---------------------------------------------------------------------------
# 8. ModuleScore + GapResult + ReadinessAssessmentRead
# ---------------------------------------------------------------------------

class TestReadiness:
    def test_module_score(self):
        ms = ModuleScore(
            module=CtdModule.m3,
            score=0.67,
            complete_count=2,
            missing_count=1,
            ambiguous_count=1,
            review_needed_count=0,
            optional_count=1,
        )
        assert ms.score == 0.67

    def test_module_score_out_of_range(self):
        with pytest.raises(ValidationError):
            ModuleScore(
                module=CtdModule.m1, score=1.01,
                complete_count=0, missing_count=0,
                ambiguous_count=0, review_needed_count=0, optional_count=0,
            )

    def test_gap_result(self):
        g = GapResult(
            gap_id="GAP-001",
            requirement_id="CTD-1.3.2",
            description="Package Leaflet missing.",
            severity=GapSeverity.high,
            recommendation="Prepare and submit Package Leaflet.",
        )
        assert g.review_status == ReviewStatus.not_started
        assert g.dossier_section_id is None

    def test_gap_list(self):
        g = GapResult(
            gap_id="GAP-001",
            requirement_id="CTD-1.3.2",
            description="Missing",
            severity=GapSeverity.high,
            recommendation="Submit.",
        )
        gl = GapList(items=[g], total=1)
        assert gl.total == 1

    def test_readiness_assessment_full(self):
        ms = ModuleScore(
            module=CtdModule.m3, score=0.5,
            complete_count=2, missing_count=2,
            ambiguous_count=0, review_needed_count=0, optional_count=1,
        )
        gap = GapResult(
            gap_id="GAP-002",
            requirement_id="CTD-3.2.S.3",
            description="Missing characterisation.",
            severity=GapSeverity.high,
            recommendation="Include structure elucidation data.",
        )
        mapping = RequirementMapping(
            requirement_id="CTD-3.2.S.3",
            status=SectionStatus.missing,
        )
        ra = ReadinessAssessmentRead(
            id=1, project_id=1, job_id=1,
            overall_score=0.62,
            summary="Moderate readiness.",
            module_scores=[ms],
            gaps=[gap],
            requirement_mappings=[mapping],
            review_status=ReviewStatus.not_started,
            algorithm_version="0.1.0",
            created_at=NOW,
        )
        assert ra.overall_score == 0.62
        assert len(ra.gaps) == 1
        assert len(ra.module_scores) == 1

    def test_readiness_score_out_of_range(self):
        with pytest.raises(ValidationError):
            ReadinessAssessmentRead(
                id=1, project_id=1, job_id=1,
                overall_score=1.5,
                summary="x",
                created_at=NOW,
            )

    def test_gap_read_alias(self):
        """GapRead must be an alias for GapResult."""
        assert GapRead is GapResult


# ---------------------------------------------------------------------------
# 9. Fixture file validation
# ---------------------------------------------------------------------------

class TestFixtureFiles:
    def test_faers_csv_loads(self):
        path = FIXTURES / "faers_demo.csv"
        assert path.exists(), "faers_demo.csv fixture is missing"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        assert len(rows) == 117, f"Expected 117 rows, got {len(rows)}"

    def test_faers_required_columns(self):
        path = FIXTURES / "faers_demo.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        required = {"primaryid", "caseid", "caseversion", "drugname", "event_term"}
        assert required.issubset(rows[0].keys())

    def test_faers_multi_version_case(self):
        """caseid 10000001 must appear with both caseversion 1 and 2."""
        path = FIXTURES / "faers_demo.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        versions = {
            r["caseversion"]
            for r in rows
            if r["caseid"] == "10000001"
        }
        assert "1" in versions and "2" in versions, (
            f"Expected both caseversions for 10000001, got: {versions}"
        )

    def test_faers_alias_events_present(self):
        path = FIXTURES / "faers_demo.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        events = {r["event_term"] for r in rows}
        assert "headache" in events
        assert "severe headache" in events

    def test_faers_strong_signal_pair(self):
        """DRUGALPHA + liver injury should be the top drug-event pair."""
        from collections import Counter
        path = FIXTURES / "faers_demo.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        counts = Counter((r["drugname"], r["event_term"]) for r in rows)
        top_drug, top_event = counts.most_common(1)[0][0]
        assert top_drug == "DRUGALPHA"
        assert top_event == "liver injury"

    def test_faers_three_drugs(self):
        path = FIXTURES / "faers_demo.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        drugs = {r["drugname"] for r in rows}
        assert drugs == {"DRUGALPHA", "DRUGBETA", "DRUGGAMMA"}

    def test_dossier_json_loads(self):
        path = FIXTURES / "dossier_outline.json"
        assert path.exists(), "dossier_outline.json fixture is missing"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "requirements" in data
        assert "sections" in data

    def test_dossier_requirements_parse(self):
        path = FIXTURES / "dossier_outline.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        reqs = [CtdRequirement(**r) for r in data["requirements"]]
        assert len(reqs) == 18

    def test_dossier_sections_parse(self):
        path = FIXTURES / "dossier_outline.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        sections = [DossierSection(**s) for s in data["sections"]]
        assert len(sections) == 18

    def test_dossier_all_statuses_covered(self):
        path = FIXTURES / "dossier_outline.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        statuses = {s["status"] for s in data["sections"]}
        assert statuses == {"complete", "missing", "ambiguous", "optional", "review_needed"}

    def test_dossier_all_modules_covered(self):
        path = FIXTURES / "dossier_outline.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        modules = {s["module"] for s in data["sections"]}
        assert modules == {"1", "2", "3", "4", "5"}

    def test_expected_results_loads(self):
        path = FIXTURES / "expected_results.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "signal_detection" in data
        assert "readiness_assessment" in data

    def test_expected_results_signal_thresholds(self):
        path = FIXTURES / "expected_results.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        sig = data["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        assert sig["prr_expected_min"] >= 2.0
        assert sig["threshold_status"] == "above"
        assert sig["rank"] == 1

    def test_expected_results_gap_requirements(self):
        path = FIXTURES / "expected_results.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        gaps = data["readiness_assessment"]["expected_gaps"]
        req_ids = [g["requirement_id"] for g in gaps]
        # Three mandatory missing sections must generate high gaps
        assert "CTD-1.3.2" in req_ids
        assert "CTD-3.2.S.3" in req_ids
        assert "CTD-5.3.1" in req_ids
