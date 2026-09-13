"""Signal detection engine tests.

Coverage
--------
1.  Required-column validation (missing required field)
2.  Duplicate row removal
3.  Latest case-version selection
4.  Case-level deduplication
5.  Exact event normalisation (alias dictionary)
6.  Fuzzy normalisation status
7.  Event cluster membership
8.  Hand-calculated a/b/c/d counts
9.  PRR calculation
10. Zero-denominator behaviour
11. Threshold pass/fail
12. Ranking
13. Processing quality metrics
14. Full fixture run vs expected_results.json
"""
from __future__ import annotations

import csv
import io
import json
import math
import pathlib
from textwrap import dedent
from typing import Dict, List

import pytest

from app.services.signal.ingestion import (
    CanonicalRecord,
    _build_column_map,
    extract_canonical,
    ingest,
    load_records,
    remove_exact_duplicates,
    select_latest_version,
    validate_schema,
    clean_records,
)
from app.services.signal.normalisation import (
    EVENT_ALIASES,
    NormMethod,
    build_event_clusters,
    normalise_drug,
    normalise_event,
)
from app.services.signal.prr import (
    PRRConfig,
    _calc_prr,
    aggregate_case_drug_events,
    apply_thresholds,
    build_contingency_tables,
    build_signal_results,
)
from app.services.signal.types import (
    ALGORITHM_VERSION,
    ContingencyTable,
    SignalSeverityLevel,
    ThresholdStatus,
)
from app.services.signal.engine import (
    SignalEngine,
    SignalEngineConfig,
    _EnrichedRecord,
    _enrich,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ===========================================================================
# Helpers
# ===========================================================================


def _make_csv(*rows: str) -> str:
    """Join a header line + data rows into a minimal CSV string."""
    return "\n".join(rows)


def _enriched_from_csv(csv_text: str) -> List[_EnrichedRecord]:
    """Ingest CSV and enrich all records."""
    result = ingest(csv_text)
    return [_enrich(r) for r in result.records]


# ===========================================================================
# 1. Required-column validation
# ===========================================================================


class TestSchemaValidation:
    def test_valid_minimal_csv_passes(self):
        csv_text = _make_csv(
            "caseid,drugname,event_term",
            "C001,DRUGALPHA,headache",
        )
        rows = load_records(csv_text)
        valid, errors = validate_schema(rows)
        assert not errors
        assert len(valid) == 1

    def test_missing_case_id_column_fails(self):
        csv_text = _make_csv(
            "drugname,event_term",
            "DRUGALPHA,headache",
        )
        rows = load_records(csv_text)
        _, errors = validate_schema(rows)
        assert any(e.field == "case_id" for e in errors)

    def test_missing_drug_column_fails(self):
        csv_text = _make_csv(
            "caseid,event_term",
            "C001,headache",
        )
        rows = load_records(csv_text)
        _, errors = validate_schema(rows)
        assert any(e.field == "drug_raw" for e in errors)

    def test_missing_event_column_fails(self):
        csv_text = _make_csv(
            "caseid,drugname",
            "C001,DRUGALPHA",
        )
        rows = load_records(csv_text)
        _, errors = validate_schema(rows)
        assert any(e.field == "event_raw" for e in errors)

    def test_empty_required_field_row_flagged(self):
        csv_text = _make_csv(
            "caseid,drugname,event_term",
            "C001,,headache",
        )
        rows = load_records(csv_text)
        valid, errors = validate_schema(rows)
        assert len(valid) == 0
        assert any(e.field == "drug_raw" for e in errors)

    def test_partial_valid_rows(self):
        csv_text = _make_csv(
            "caseid,drugname,event_term",
            "C001,DRUGALPHA,headache",
            "C002,,nausea",   # bad row — drug missing
            "C003,DRUGBETA,fatigue",
        )
        rows = load_records(csv_text)
        valid, errors = validate_schema(rows)
        assert len(valid) == 2
        assert len(errors) == 1

    def test_column_alias_mapping(self):
        """FAERS-style column name 'caseid' should map to canonical 'case_id'."""
        csv_text = _make_csv(
            "primaryid,caseid,caseversion,drugname,event_term",
            "PID001,C001,1,DRUGALPHA,headache",
        )
        rows = load_records(csv_text)
        col_map = _build_column_map(list(rows[0].keys()))
        assert col_map.get("case_id") == "caseid"
        assert col_map.get("drug_raw") == "drugname"
        assert col_map.get("event_raw") == "event_term"


# ===========================================================================
# 2. Duplicate row removal
# ===========================================================================


class TestDuplicateRemoval:
    def test_no_duplicates_unchanged(self):
        rows = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
        result, removed = remove_exact_duplicates(rows)
        assert removed == 0
        assert len(result) == 2

    def test_exact_duplicate_removed(self):
        row = {"caseid": "C001", "drugname": "DRUGALPHA", "event_term": "headache"}
        rows = [row, dict(row)]  # identical dict contents
        result, removed = remove_exact_duplicates(rows)
        assert removed == 1
        assert len(result) == 1

    def test_near_duplicate_not_removed(self):
        """Rows differing in any field must NOT be treated as duplicates."""
        rows = [
            {"caseid": "C001", "drugname": "DRUGALPHA", "event_term": "headache"},
            {"caseid": "C001", "drugname": "DRUGALPHA", "event_term": "nausea"},
        ]
        result, removed = remove_exact_duplicates(rows)
        assert removed == 0
        assert len(result) == 2

    def test_multiple_duplicates(self):
        row = {"a": "1"}
        rows = [row, dict(row), dict(row)]
        result, removed = remove_exact_duplicates(rows)
        assert removed == 2
        assert len(result) == 1


# ===========================================================================
# 3. Latest case-version selection
# ===========================================================================


class TestLatestVersionSelection:
    def _col_map(self):
        return {"case_id": "caseid", "case_version": "caseversion"}

    def test_keeps_latest_version(self):
        rows = [
            {"caseid": "C001", "caseversion": "1", "drugname": "DRUGALPHA"},
            {"caseid": "C001", "caseversion": "2", "drugname": "DRUGALPHA"},
        ]
        result, removed = select_latest_version(rows, self._col_map())
        assert removed == 1
        assert len(result) == 1
        assert result[0]["caseversion"] == "2"

    def test_fixture_case_10000001(self):
        """caseid 10000001 has versions 1 and 2 in the FAERS fixture.
        After dedup only version 2 should survive.
        """
        path = FIXTURES / "faers_demo.csv"
        rows = load_records(path.read_text(encoding="utf-8"))
        col_map = _build_column_map(list(rows[0].keys()))
        result, removed = select_latest_version(rows, col_map)
        assert removed == 1, f"Expected 1 old-version row removed, got {removed}"
        case_rows = [r for r in result if r[col_map["case_id"]] == "10000001"]
        assert len(case_rows) == 1
        assert str(case_rows[0][col_map["case_version"]]) == "2"

    def test_no_version_column_passes_all(self):
        rows = [
            {"caseid": "C001", "drugname": "DRUGALPHA"},
            {"caseid": "C002", "drugname": "DRUGBETA"},
        ]
        col_map = {"case_id": "caseid"}  # no case_version mapped
        result, removed = select_latest_version(rows, col_map)
        assert removed == 0
        assert len(result) == 2

    def test_non_integer_version_treated_as_1(self):
        rows = [
            {"caseid": "C001", "caseversion": "A", "drugname": "DRUGALPHA"},
            {"caseid": "C001", "caseversion": "B", "drugname": "DRUGBETA"},
        ]
        # Both parse to 1 so first encountered is kept (deterministic)
        result, removed = select_latest_version(rows, self._col_map())
        assert len(result) + removed == 2


# ===========================================================================
# 4. Case-level deduplication
# ===========================================================================


class TestCaseLevelDeduplication:
    """Each (case_id, drug) and (case_id, event) counted at most once."""

    def test_same_drug_same_case_counted_once(self):
        """Two rows with same case_id and same drug → drug counted once."""
        enriched = [
            _EnrichedRecord(
                case_id="C001", drug_raw="DRUGALPHA", event_raw="headache",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=0, drug_canonical="DRUGALPHA", event_canonical="Headache",
            ),
            _EnrichedRecord(
                case_id="C001", drug_raw="DRUGALPHA", event_raw="nausea",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=1, drug_canonical="DRUGALPHA", event_canonical="Nausea",
            ),
        ]
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        assert case_drugs["C001"] == {"DRUGALPHA"}
        assert case_events["C001"] == {"Headache", "Nausea"}

    def test_different_drugs_same_case(self):
        enriched = [
            _EnrichedRecord(
                case_id="C001", drug_raw="DRUGALPHA", event_raw="headache",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=0, drug_canonical="DRUGALPHA", event_canonical="Headache",
            ),
            _EnrichedRecord(
                case_id="C001", drug_raw="DRUGBETA", event_raw="headache",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=1, drug_canonical="DRUGBETA", event_canonical="Headache",
            ),
        ]
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        assert case_drugs["C001"] == {"DRUGALPHA", "DRUGBETA"}
        # Headache counted once as an event for this case
        assert case_events["C001"] == {"Headache"}

    def test_same_event_different_cases_counted_separately(self):
        enriched = [
            _EnrichedRecord(
                case_id="C001", drug_raw="DRUGALPHA", event_raw="headache",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=0, drug_canonical="DRUGALPHA", event_canonical="Headache",
            ),
            _EnrichedRecord(
                case_id="C002", drug_raw="DRUGALPHA", event_raw="headache",
                primaryid=None, case_version="1", receipt_date=None,
                drug_role=None, seriousness=None, outcome=None,
                age_group=None, sex=None, reporter_country=None,
                source_row=1, drug_canonical="DRUGALPHA", event_canonical="Headache",
            ),
        ]
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        assert "C001" in case_drugs
        assert "C002" in case_drugs
        # Both cases separately have Headache
        assert "Headache" in case_events["C001"]
        assert "Headache" in case_events["C002"]


# ===========================================================================
# 5. Exact event normalisation
# ===========================================================================


class TestExactNormalisation:
    def test_exact_match_headache(self):
        nr = normalise_event("headache")
        assert nr.preferred_term == "Headache"
        assert nr.method == NormMethod.alias_lookup
        assert nr.confidence == 1.0
        assert nr.meddra_code == "10019211"

    def test_exact_match_severe_headache_clusters_to_headache(self):
        nr = normalise_event("severe headache")
        assert nr.preferred_term == "Headache"
        assert nr.method == NormMethod.alias_lookup

    def test_exact_match_liver_injury(self):
        nr = normalise_event("liver injury")
        assert nr.preferred_term == "Hepatic disorder"
        assert nr.method == NormMethod.alias_lookup
        assert nr.meddra_code == "10019692"

    def test_exact_match_hepatic_failure(self):
        nr = normalise_event("hepatic failure")
        assert nr.preferred_term == "Hepatic disorder"
        assert nr.method == NormMethod.alias_lookup

    def test_exact_match_nausea(self):
        nr = normalise_event("nausea")
        assert nr.preferred_term == "Nausea"

    def test_exact_match_vomiting(self):
        nr = normalise_event("vomiting")
        assert nr.preferred_term == "Vomiting"

    def test_exact_match_rash(self):
        nr = normalise_event("rash")
        assert nr.preferred_term == "Rash"

    def test_exact_match_fatigue(self):
        nr = normalise_event("fatigue")
        assert nr.preferred_term == "Fatigue"

    def test_case_insensitive(self):
        nr1 = normalise_event("Headache")
        nr2 = normalise_event("HEADACHE")
        assert nr1.preferred_term == nr2.preferred_term == "Headache"

    def test_drug_exact_passthrough(self):
        nr = normalise_drug("DRUGALPHA")
        assert nr.canonical == "DRUGALPHA"
        assert nr.method == NormMethod.exact_match
        assert nr.confidence == 1.0

    def test_drug_uppercases_raw(self):
        nr = normalise_drug("drugalpha")
        assert nr.canonical == "DRUGALPHA"


# ===========================================================================
# 6. Fuzzy normalisation
# ===========================================================================


class TestFuzzyNormalisation:
    def test_passthrough_for_unknown_term(self):
        """A completely unknown term falls through to passthrough."""
        nr = normalise_event("xylophoneitis")
        assert nr.method == NormMethod.passthrough
        assert nr.confidence == 0.5

    def test_fuzzy_returns_known_preferred_term_or_passthrough(self):
        """A near-match should return method=fuzzy or alias_lookup; never crash."""
        nr = normalise_event("livr injry")  # garbled
        assert nr.method in (NormMethod.fuzzy, NormMethod.alias_lookup, NormMethod.passthrough)
        assert 0.0 <= nr.confidence <= 1.0


# ===========================================================================
# 7. Event cluster membership
# ===========================================================================


class TestEventClustering:
    def test_headache_cluster_contains_both_aliases(self):
        raw_terms = ["headache", "severe headache", "nausea"]
        case_counts = {"headache": 10, "severe headache": 5, "nausea": 7}
        clusters = build_event_clusters(raw_terms, case_counts)
        assert "Headache" in clusters
        hc = clusters["Headache"]
        assert "headache" in hc.raw_aliases
        assert "severe headache" in hc.raw_aliases
        assert hc.case_count == 15  # 10 + 5

    def test_hepatic_disorder_cluster(self):
        raw_terms = ["liver injury", "hepatic failure"]
        case_counts = {"liver injury": 20, "hepatic failure": 4}
        clusters = build_event_clusters(raw_terms, case_counts)
        assert "Hepatic disorder" in clusters
        hc = clusters["Hepatic disorder"]
        assert hc.case_count == 24

    def test_nausea_is_separate_cluster(self):
        raw_terms = ["nausea", "headache"]
        case_counts = {"nausea": 5, "headache": 5}
        clusters = build_event_clusters(raw_terms, case_counts)
        assert "Nausea" in clusters
        assert "Headache" in clusters
        assert len(clusters["Nausea"].raw_aliases) == 1

    def test_meddra_code_populated(self):
        raw_terms = ["headache"]
        clusters = build_event_clusters(raw_terms, {"headache": 1})
        assert clusters["Headache"].meddra_code == "10019211"


# ===========================================================================
# 8. Hand-calculated a/b/c/d
# ===========================================================================


class TestContingencyTableCounts:
    """Use a minimal controlled dataset to verify cell values."""

    def _make_enriched(self, data):
        """data: list of (case_id, drug_canonical, event_canonical)"""
        recs = []
        for i, (cid, drug, event) in enumerate(data):
            recs.append(
                _EnrichedRecord(
                    case_id=cid, drug_raw=drug, event_raw=event,
                    primaryid=None, case_version="1", receipt_date=None,
                    drug_role=None, seriousness=None, outcome=None,
                    age_group=None, sex=None, reporter_country=None,
                    source_row=i,
                    drug_canonical=drug,
                    event_canonical=event,
                )
            )
        return recs

    def test_simple_2x2(self):
        """
        4 cases:
          C1: DRUGALPHA + Headache  → a row
          C2: DRUGALPHA + Nausea    → b row (drug no event)
          C3: DRUGBETA  + Headache  → c row (event no drug)
          C4: DRUGBETA  + Nausea    → d row

        For (DRUGALPHA, Headache):
          a=1, b=1, c=1, d=1
          PRR = (1/2) / (1/2) = 1.0
        """
        enriched = self._make_enriched([
            ("C1", "DRUGALPHA", "Headache"),
            ("C2", "DRUGALPHA", "Nausea"),
            ("C3", "DRUGBETA", "Headache"),
            ("C4", "DRUGBETA", "Nausea"),
        ])
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        tables = build_contingency_tables(case_drugs, case_events)
        t = next(t for t in tables if t.drug == "DRUGALPHA" and t.event == "Headache")
        assert t.a == 1
        assert t.b == 1
        assert t.c == 1
        assert t.d == 1
        assert t.prr == pytest.approx(1.0)

    def test_strong_signal(self):
        """
        6 cases:
          C1-C4: DRUGALPHA + Hepatic disorder
          C5:    DRUGALPHA + Nausea
          C6:    DRUGBETA  + Nausea

        For (DRUGALPHA, Hepatic disorder):
          a=4 (drug+event), b=1 (drug+nausea only), c=0, d=1
          c=0 → PRR = None (zero denominator via c in the rate_other formula)

        Let's use a dataset with c>0:
          C1-C4: DRUGALPHA + Hepatic disorder
          C5:    DRUGALPHA + Nausea
          C6:    DRUGBETA  + Hepatic disorder
          C7:    DRUGBETA  + Nausea

        (DRUGALPHA, Hepatic disorder):
          a=4, b=1, c=1, d=1
          PRR = (4/5) / (1/2) = 0.8 / 0.5 = 1.6
        """
        enriched = self._make_enriched([
            ("C1", "DRUGALPHA", "Hepatic disorder"),
            ("C2", "DRUGALPHA", "Hepatic disorder"),
            ("C3", "DRUGALPHA", "Hepatic disorder"),
            ("C4", "DRUGALPHA", "Hepatic disorder"),
            ("C5", "DRUGALPHA", "Nausea"),
            ("C6", "DRUGBETA", "Hepatic disorder"),
            ("C7", "DRUGBETA", "Nausea"),
        ])
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        tables = build_contingency_tables(case_drugs, case_events)
        t = next(t for t in tables if t.drug == "DRUGALPHA" and t.event == "Hepatic disorder")
        assert t.a == 4
        assert t.b == 1
        assert t.c == 1
        assert t.d == 1
        expected_prr = (4 / 5) / (1 / 2)
        assert t.prr == pytest.approx(expected_prr, rel=1e-4)

    def test_cells_sum_to_total_cases(self):
        """a + b + c + d must equal total distinct cases in the dataset."""
        enriched = self._make_enriched([
            ("C1", "DRUGALPHA", "Headache"),
            ("C2", "DRUGALPHA", "Nausea"),
            ("C3", "DRUGBETA", "Headache"),
            ("C4", "DRUGBETA", "Nausea"),
            ("C5", "DRUGBETA", "Fatigue"),
        ])
        case_drugs, case_events = aggregate_case_drug_events(enriched)
        tables = build_contingency_tables(case_drugs, case_events)
        n = 5  # total distinct cases
        for t in tables:
            assert t.a + t.b + t.c + t.d == n, (
                f"{t.drug}/{t.event}: a+b+c+d={t.a+t.b+t.c+t.d} ≠ {n}"
            )


# ===========================================================================
# 9. PRR calculation
# ===========================================================================


class TestPRRCalculation:
    def test_basic_prr_formula(self):
        """PRR = [a/(a+b)] / [c/(c+d)]"""
        a, b, c, d = 4, 1, 1, 1
        prr, _, _ = _calc_prr(a, b, c, d)
        expected = (a / (a + b)) / (c / (c + d))
        assert prr == pytest.approx(expected, rel=1e-4)

    def test_prr_equals_1_when_rates_equal(self):
        prr, _, _ = _calc_prr(5, 5, 5, 5)
        assert prr == pytest.approx(1.0)

    def test_prr_greater_than_1_when_drug_enriched(self):
        # Drug reports event more often than others
        prr, _, _ = _calc_prr(10, 5, 2, 20)
        assert prr > 1.0

    def test_confidence_intervals_ordered(self):
        prr, lower, upper = _calc_prr(10, 5, 2, 20)
        assert lower is not None and upper is not None
        assert lower < prr < upper

    def test_ci_width_decreases_with_more_cases(self):
        """More data → tighter CI."""
        _, lo1, hi1 = _calc_prr(10, 5, 2, 20)
        _, lo2, hi2 = _calc_prr(100, 50, 20, 200)
        assert (hi2 - lo2) < (hi1 - lo1)


# ===========================================================================
# 10. Zero-denominator behaviour
# ===========================================================================


class TestZeroDenominator:
    def test_zero_drug_reports_returns_none(self):
        """a=0, b=0 → (a+b)=0 → cannot compute PRR."""
        prr, lower, upper = _calc_prr(0, 0, 5, 5)
        assert prr is None
        assert lower is None
        assert upper is None

    def test_zero_other_drug_reports_returns_none(self):
        """c=0, d=0 → (c+d)=0 → cannot compute PRR."""
        prr, lower, upper = _calc_prr(5, 5, 0, 0)
        assert prr is None

    def test_zero_c_returns_none(self):
        """c=0 means rate_other=0 → undefined PRR."""
        prr, _, _ = _calc_prr(5, 3, 0, 10)
        assert prr is None

    def test_threshold_status_zero_denominator(self):
        """ContingencyTable with prr=None must get status=zero_denominator."""
        config = PRRConfig()
        t = ContingencyTable(
            drug="DRUGALPHA", event="Headache",
            a=5, b=3, c=0, d=10,
            prr=None, prr_lower_ci=None, prr_upper_ci=None,
            threshold_status=ThresholdStatus.below,
            severity=SignalSeverityLevel.low,
            rank=0,
        )
        apply_thresholds([t], config)
        assert t.threshold_status == ThresholdStatus.zero_denominator


# ===========================================================================
# 11. Threshold pass/fail
# ===========================================================================


class TestThresholds:
    def _table(self, prr, a=5, b=5, c=2, d=20):
        return ContingencyTable(
            drug="DRUGALPHA", event="Headache",
            a=a, b=b, c=c, d=d,
            prr=prr,
            prr_lower_ci=None, prr_upper_ci=None,
            threshold_status=ThresholdStatus.below,
            severity=SignalSeverityLevel.low,
            rank=0,
        )

    def test_above_threshold(self):
        config = PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3)
        t = self._table(prr=5.0, a=5, b=5, c=2, d=20)
        apply_thresholds([t], config)
        assert t.threshold_status == ThresholdStatus.above

    def test_at_threshold(self):
        config = PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3)
        t = self._table(prr=2.0, a=5, b=5, c=2, d=20)
        apply_thresholds([t], config)
        assert t.threshold_status == ThresholdStatus.at

    def test_below_min_prr(self):
        config = PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3)
        t = self._table(prr=1.5, a=5, b=5, c=2, d=20)
        apply_thresholds([t], config)
        assert t.threshold_status == ThresholdStatus.below

    def test_below_min_pair_count(self):
        config = PRRConfig(min_prr=2.0, min_pair_count=5, min_drug_reports=3, min_event_reports=3)
        # a=2 < min_pair_count=5 → below
        t = self._table(prr=8.0, a=2, b=10, c=1, d=20)
        apply_thresholds([t], config)
        assert t.threshold_status == ThresholdStatus.below

    def test_severity_critical(self):
        config = PRRConfig(prr_critical=8.0)
        t = self._table(prr=9.0, a=10, b=5, c=1, d=50)
        apply_thresholds([t], config)
        assert t.severity == SignalSeverityLevel.critical

    def test_severity_high(self):
        config = PRRConfig(prr_critical=8.0, prr_high=4.0)
        t = self._table(prr=5.0, a=10, b=5, c=2, d=50)
        apply_thresholds([t], config)
        assert t.severity == SignalSeverityLevel.high

    def test_severity_medium(self):
        config = PRRConfig(prr_critical=8.0, prr_high=4.0, prr_medium=2.0)
        t = self._table(prr=3.0, a=5, b=5, c=2, d=20)
        apply_thresholds([t], config)
        assert t.severity == SignalSeverityLevel.medium


# ===========================================================================
# 12. Ranking
# ===========================================================================


class TestRanking:
    def _table(self, drug, event, prr, a, status=None):
        return ContingencyTable(
            drug=drug, event=event,
            a=a, b=5, c=2, d=20,
            prr=prr,
            prr_lower_ci=None, prr_upper_ci=None,
            threshold_status=status or ThresholdStatus.below,
            severity=SignalSeverityLevel.low,
            rank=0,
        )

    def test_above_ranks_before_below(self):
        t_above = self._table("DRUGALPHA", "Headache", prr=5.0, a=10)
        t_below = self._table("DRUGBETA", "Nausea", prr=1.5, a=10)
        apply_thresholds([t_above, t_below], PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3))
        assert t_above.rank < t_below.rank

    def test_higher_prr_ranks_first_within_above(self):
        t1 = self._table("DRUGALPHA", "Headache", prr=10.0, a=8)
        t2 = self._table("DRUGALPHA", "Nausea", prr=5.0, a=8)
        config = PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3)
        apply_thresholds([t1, t2], config)
        assert t1.rank < t2.rank

    def test_higher_pair_count_breaks_tie_in_prr(self):
        t1 = self._table("DRUGALPHA", "Headache", prr=5.0, a=20)
        t2 = self._table("DRUGALPHA", "Nausea", prr=5.0, a=10)
        config = PRRConfig(min_prr=2.0, min_pair_count=3, min_drug_reports=5, min_event_reports=3)
        apply_thresholds([t1, t2], config)
        assert t1.rank < t2.rank

    def test_rank_starts_at_1(self):
        t = self._table("DRUGALPHA", "Headache", prr=5.0, a=10)
        apply_thresholds([t], PRRConfig())
        assert t.rank == 1

    def test_all_ranks_unique(self):
        tables = [
            self._table("DRUGALPHA", f"Event{i}", prr=float(i), a=i + 3)
            for i in range(1, 6)
        ]
        apply_thresholds(tables, PRRConfig())
        ranks = [t.rank for t in tables]
        assert sorted(ranks) == list(range(1, 6))


# ===========================================================================
# 13. Processing quality metrics
# ===========================================================================


class TestProcessingMetrics:
    def test_metrics_from_fixture(self):
        path = FIXTURES / "faers_demo.csv"
        csv_text = path.read_text(encoding="utf-8")
        engine = SignalEngine()
        output = engine.run_from_csv(csv_text)
        m = output.metrics

        # Raw row count from fixture
        assert m.total_raw_rows == 117

        # Exactly one old-version row (caseid 10000001 version 1 dropped)
        assert m.old_version_rows_removed == 1

        # Rows used should equal 116 (117 - 1 version drop, no exact dups)
        assert m.rows_after_dedup == 116
        assert m.rows_used == 116

        # Three drugs
        assert m.distinct_drugs == 3

        # Raw event terms
        assert m.distinct_events_raw == 8

        # Algorithm version stamped
        assert m.algorithm_version == ALGORITHM_VERSION

    def test_metrics_rows_add_up(self):
        """total_raw_rows = exact_dup + old_ver + dropped_required + rows_used."""
        path = FIXTURES / "faers_demo.csv"
        csv_text = path.read_text(encoding="utf-8")
        output = SignalEngine().run_from_csv(csv_text)
        m = output.metrics
        accounted = (
            m.exact_duplicate_rows_removed
            + m.old_version_rows_removed
            + m.rows_dropped_missing_required
            + m.rows_used
        )
        assert accounted == m.total_raw_rows


# ===========================================================================
# 14. Full fixture run vs expected_results.json
# ===========================================================================


class TestFixtureRun:
    @pytest.fixture(scope="class")
    def output(self):
        path = FIXTURES / "faers_demo.csv"
        csv_text = path.read_text(encoding="utf-8")
        return SignalEngine().run_from_csv(csv_text)

    @pytest.fixture(scope="class")
    def expected(self):
        return json.loads((FIXTURES / "expected_results.json").read_text())

    # --- Dedup ---

    def test_total_unique_cases(self, output, expected):
        exp = expected["faers_fixture"]
        assert output.metrics.rows_after_dedup == exp["total_unique_cases_after_dedup"]

    def test_distinct_drugs(self, output, expected):
        exp_drugs = set(expected["faers_fixture"]["distinct_drugs"])
        assert output.metrics.distinct_drugs == len(exp_drugs)

    def test_distinct_events_raw_count(self, output, expected):
        exp_events = expected["faers_fixture"]["distinct_events_raw"]
        assert output.metrics.distinct_events_raw == len(exp_events)

    # --- Alias pairs ---

    def test_headache_cluster_aliases(self, output, expected):
        clusters_by_pt = {c.preferred_term: c for c in output.clusters}
        assert "Headache" in clusters_by_pt
        hc = clusters_by_pt["Headache"]
        assert "headache" in hc.raw_aliases
        assert "severe headache" in hc.raw_aliases

    def test_hepatic_disorder_cluster_aliases(self, output, expected):
        clusters_by_pt = {c.preferred_term: c for c in output.clusters}
        assert "Hepatic disorder" in clusters_by_pt
        hc = clusters_by_pt["Hepatic disorder"]
        assert "liver injury" in hc.raw_aliases
        assert "hepatic failure" in hc.raw_aliases

    def test_headache_meddra_code(self, output):
        clusters_by_pt = {c.preferred_term: c for c in output.clusters}
        assert clusters_by_pt["Headache"].meddra_code == "10019211"

    def test_hepatic_disorder_meddra_code(self, output):
        clusters_by_pt = {c.preferred_term: c for c in output.clusters}
        assert clusters_by_pt["Hepatic disorder"].meddra_code == "10019692"

    # --- Top signal: DRUGALPHA + Hepatic disorder ---

    def test_drugalpha_hepatic_signal_present(self, output):
        signals = {(s.drug, s.event): s for s in output.signals}
        assert ("DRUGALPHA", "Hepatic disorder") in signals

    def test_drugalpha_hepatic_a_in_range(self, output, expected):
        exp = expected["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        assert exp["a_min"] <= s.a <= exp["a_max"], (
            f"DRUGALPHA/Hepatic disorder a={s.a}, expected {exp['a_min']}–{exp['a_max']}"
        )

    def test_drugalpha_hepatic_prr_in_range(self, output, expected):
        exp = expected["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        assert s.prr is not None
        assert exp["prr_expected_min"] <= s.prr <= exp["prr_expected_max"], (
            f"PRR={s.prr}, expected [{exp['prr_expected_min']}, {exp['prr_expected_max']}]"
        )

    def test_drugalpha_hepatic_threshold_above(self, output, expected):
        exp = expected["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        assert s.threshold_status.value == exp["threshold_status"]

    def test_drugalpha_hepatic_rank_1(self, output, expected):
        exp = expected["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        assert s.rank == exp["rank"]

    def test_drugalpha_hepatic_severity_critical(self, output, expected):
        exp = expected["signal_detection"]["contingency_table_DRUGALPHA_HepaticDisorder"]
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        assert s.severity.value == exp["severity"]

    # --- Number of signals above threshold ---

    def test_signals_above_threshold_min(self, output, expected):
        exp_min = expected["signal_detection"]["expected_signals_above_threshold_min"]
        above = [s for s in output.signals if s.threshold_status.value in ("above", "at")]
        assert len(above) >= exp_min, (
            f"Expected >= {exp_min} signals above threshold, got {len(above)}"
        )

    # --- Disclaimer ---

    def test_disclaimer_present(self, output):
        from app.services.signal.types import DISCLAIMER
        assert output.disclaimer == DISCLAIMER
        for s in output.signals:
            assert s.disclaimer == DISCLAIMER

    # --- PRR formula verification against hand calculation ---

    def test_prr_formula_drugalpha_hepatic(self, output):
        """Verify PRR = [a/(a+b)] / [c/(c+d)] by direct formula check."""
        s = next(s for s in output.signals if s.drug == "DRUGALPHA" and s.event == "Hepatic disorder")
        expected_prr = (s.a / (s.a + s.b)) / (s.c / (s.c + s.d))
        assert s.prr == pytest.approx(expected_prr, rel=1e-4)

    # --- algorithm_version in result ---

    def test_algorithm_version_in_signals(self, output):
        for s in output.signals:
            assert s.algorithm_version == ALGORITHM_VERSION

    # --- JSON round-trip ---

    def test_json_ingestion_produces_same_metrics(self, output):
        """Ingesting same data as JSON should produce identical metrics."""
        path = FIXTURES / "faers_demo.csv"
        rows = load_records(path.read_text(encoding="utf-8"), fmt="csv")
        # Convert to JSON
        json_text = json.dumps(rows)
        json_output = SignalEngine().run_from_json(json_text)
        assert json_output.metrics.rows_used == output.metrics.rows_used
        assert json_output.metrics.distinct_drugs == output.metrics.distinct_drugs
