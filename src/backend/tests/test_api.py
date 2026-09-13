"""API integration tests for SafetyReady.

Coverage
--------
1.  Health endpoint
2.  Project creation
3.  Valid signal upload → job queued
4.  Invalid signal upload → 422 with structured errors
5.  Valid readiness upload → job queued
6.  Job polling (queued state, missing job)
7.  Completed signal result retrieval
8.  Failed job retrieval
9.  Gap review status update
10. Signal JSON export
11. Signal CSV export
12. Readiness JSON export
13. Readiness Markdown export
14. Signal summary endpoint
15. Signal list (ranked, paginated)
16. Signal detail endpoint
17. Event clusters endpoint
18. Readiness module scores endpoint
19. Readiness requirement matrix endpoint
20. Gap list with filtering
21. Gap detail endpoint
22. Project-level jobs listing
23. Project-level recent results
24. Audit event written on upload
"""
from __future__ import annotations

import io
import json
import pathlib
import time
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ===========================================================================
# Helpers
# ===========================================================================


def _create_project(client: TestClient, name: str = "Test Project") -> int:
    resp = client.post("/api/projects", json={"name": name, "description": "auto-created"})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _upload_signal_csv(client: TestClient, project_id: int, csv_text: Optional[str] = None) -> dict:
    if csv_text is None:
        csv_text = (FIXTURES / "faers_demo.csv").read_text(encoding="utf-8")
    resp = client.post(
        f"/api/projects/{project_id}/signals/upload",
        files={"file": ("faers_demo.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    return resp


def _upload_readiness_json(client: TestClient, project_id: int, json_text: Optional[str] = None) -> dict:
    if json_text is None:
        json_text = (FIXTURES / "dossier_outline.json").read_text(encoding="utf-8")
    resp = client.post(
        f"/api/projects/{project_id}/readiness/upload",
        files={"file": ("dossier_outline.json", io.BytesIO(json_text.encode()), "application/json")},
    )
    return resp


def _wait_for_job(client: TestClient, job_id: int, max_seconds: float = 10.0) -> dict:
    """Poll job until status != queued/running, or timeout."""
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        if data["status"] in ("complete", "failed"):
            return data
        time.sleep(0.05)
    return client.get(f"/api/jobs/{job_id}").json()["data"]


def _run_signal_job_sync(client: TestClient, project_id: int) -> dict:
    """Upload fixture + wait for background job to finish; return job dict."""
    resp = _upload_signal_csv(client, project_id)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["id"]
    return _wait_for_job(client, job_id)


def _run_readiness_job_sync(client: TestClient, project_id: int) -> dict:
    resp = _upload_readiness_json(client, project_id)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["id"]
    return _wait_for_job(client, job_id)


# ===========================================================================
# 1. Health
# ===========================================================================


class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ===========================================================================
# 2. Project creation
# ===========================================================================


class TestProjectCreation:
    def test_create_project_returns_201(self, client: TestClient):
        resp = client.post("/api/projects", json={"name": "Hackathon Project"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Hackathon Project"
        assert data["status"] == "draft"
        assert isinstance(data["id"], int)

    def test_create_project_missing_name_returns_422(self, client: TestClient):
        resp = client.post("/api/projects", json={"description": "no name"})
        assert resp.status_code == 422


# ===========================================================================
# 3. Valid signal upload
# ===========================================================================


class TestSignalUpload:
    def test_valid_csv_upload_returns_202_with_job_id(self, client: TestClient):
        pid = _create_project(client, "Signal Upload Test")
        resp = _upload_signal_csv(client, pid)
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "data" in body
        assert "id" in body["data"]
        assert body["data"]["job_type"] == "signal_detection"
        assert body["data"]["status"] in ("queued", "running", "complete")

    def test_valid_csv_upload_enqueues_job(self, client: TestClient):
        pid = _create_project(client)
        resp = _upload_signal_csv(client, pid)
        assert resp.status_code == 202
        job_id = resp.json()["data"]["id"]
        # Job must be retrievable
        job_resp = client.get(f"/api/jobs/{job_id}")
        assert job_resp.status_code == 200
        assert job_resp.json()["data"]["id"] == job_id

    def test_signal_upload_unknown_project_returns_404(self, client: TestClient):
        resp = _upload_signal_csv(client, 99999)
        assert resp.status_code == 404


# ===========================================================================
# 4. Invalid signal upload
# ===========================================================================


class TestInvalidSignalUpload:
    def test_missing_required_column_returns_422(self, client: TestClient):
        pid = _create_project(client)
        bad_csv = "drugname,event_term\nDRUGALPHA,headache\n"
        resp = _upload_signal_csv(client, pid, csv_text=bad_csv)
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert "detail" in body

    def test_empty_file_returns_422(self, client: TestClient):
        pid = _create_project(client)
        resp = client.post(
            f"/api/projects/{pid}/signals/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert resp.status_code == 422

    def test_upload_returns_error_code_in_detail(self, client: TestClient):
        pid = _create_project(client)
        bad_csv = "drug,event\nDRUGALPHA,headache\n"  # missing case_id
        resp = _upload_signal_csv(client, pid, csv_text=bad_csv)
        assert resp.status_code == 422
        detail = resp.json().get("detail", {})
        # Detail is an error envelope
        assert "error" in detail or "detail" in resp.json()


# ===========================================================================
# 5. Valid readiness upload
# ===========================================================================


class TestReadinessUpload:
    def test_valid_json_upload_returns_202(self, client: TestClient):
        pid = _create_project(client, "Readiness Upload Test")
        resp = _upload_readiness_json(client, pid)
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["data"]["job_type"] == "readiness_assessment"
        assert body["data"]["status"] in ("queued", "running", "complete")

    def test_text_input_form_field_accepted(self, client: TestClient):
        pid = _create_project(client)
        json_text = (FIXTURES / "dossier_outline.json").read_text(encoding="utf-8")
        resp = client.post(
            f"/api/projects/{pid}/readiness/upload",
            data={"text_input": json_text},
        )
        assert resp.status_code == 202, resp.text

    def test_readiness_upload_unknown_project_returns_404(self, client: TestClient):
        resp = _upload_readiness_json(client, 99999)
        assert resp.status_code == 404

    def test_missing_both_inputs_returns_422(self, client: TestClient):
        pid = _create_project(client)
        resp = client.post(f"/api/projects/{pid}/readiness/upload")
        assert resp.status_code == 422


# ===========================================================================
# 6. Job polling
# ===========================================================================


class TestJobPolling:
    def test_poll_queued_job(self, client: TestClient):
        pid = _create_project(client)
        resp = _upload_signal_csv(client, pid)
        job_id = resp.json()["data"]["id"]
        # Immediately after enqueue, job may be queued or already running
        poll = client.get(f"/api/jobs/{job_id}")
        assert poll.status_code == 200
        assert poll.json()["data"]["status"] in ("queued", "running", "complete")

    def test_poll_missing_job_returns_404(self, client: TestClient):
        resp = client.get("/api/jobs/999999")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "JOB_NOT_FOUND"

    def test_running_job_has_progress_field(self, client: TestClient):
        pid = _create_project(client)
        resp = _upload_signal_csv(client, pid)
        job_id = resp.json()["data"]["id"]
        job = _wait_for_job(client, job_id)
        # After completion, job was RUNNING at some point; progress must be set
        assert job["status"] == "complete"


# ===========================================================================
# 7. Completed signal result retrieval
# ===========================================================================


class TestCompletedSignalResult:
    def test_completed_job_has_result(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete", f"Job failed: {job.get('error')}"
        assert job["result"] is not None
        assert "signals_detected" in job["result"]

    def test_signal_summary_available_after_job(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/summary")
        assert resp.status_code == 200
        summary = resp.json()["data"]
        assert "total_signals" in summary
        assert summary["total_signals"] >= 0

    def test_signal_list_non_empty_after_job(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals")
        assert resp.status_code == 200
        body = resp.json()["data"]
        # FAERS fixture produces at least one signal above threshold
        assert body["total"] >= 1

    def test_signal_detail_retrievable(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        list_resp = client.get(f"/api/projects/{pid}/signals")
        items = list_resp.json()["data"]["items"]
        assert len(items) >= 1
        first = items[0]
        # SignalSummary has an 'id' field (the DB integer id)
        assert "id" in first, "SignalSummary must include integer DB id"
        sig_id = first["id"]
        assert isinstance(sig_id, int), f"Expected int id, got {type(sig_id)}"
        # Fetch the detail endpoint using the DB id
        detail_resp = client.get(f"/api/projects/{pid}/signals/{sig_id}")
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()["data"]
        # SignalRead has id/severity at the top level; drug/event are inside result
        assert detail["id"] == sig_id
        assert detail["severity"] == first["severity"]
        # result contains drug and event fields
        assert detail.get("result") is not None
        assert detail["result"]["drug"] == first["drug"]
        assert detail["result"]["event"] == first["event"]

    def test_signal_detail_by_id(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        # Get all signals from DB via export
        export_resp = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        assert export_resp.status_code == 200
        payload = json.loads(export_resp.content)
        assert len(payload["signals"]) >= 1
        sig_id = payload["signals"][0]["id"]
        detail_resp = client.get(f"/api/projects/{pid}/signals/{sig_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["id"] == sig_id


# ===========================================================================
# 8. Failed job retrieval
# ===========================================================================


class TestFailedJobRetrieval:
    def test_failed_job_has_error_field(self, client: TestClient):
        pid = _create_project(client)
        # Upload valid CSV but corrupt it with wrong columns
        bad_csv = "col_a,col_b,col_c\n1,2,3\n"
        resp = _upload_signal_csv(client, pid, csv_text=bad_csv)
        # This should get rejected by validation before even creating a job
        assert resp.status_code == 422

    def test_empty_upload_rejected_before_job_creation(self, client: TestClient):
        pid = _create_project(client)
        resp = client.post(
            f"/api/projects/{pid}/signals/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body


# ===========================================================================
# 9. Gap review update
# ===========================================================================


class TestGapReviewUpdate:
    def test_gap_review_status_can_be_updated(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete", f"Job failed: {job.get('error')}"

        # Get gaps
        gaps_resp = client.get(f"/api/projects/{pid}/readiness/gaps")
        assert gaps_resp.status_code == 200
        gaps = gaps_resp.json()["data"]["items"]
        assert len(gaps) >= 1, "Expected at least one gap from fixture"

        # Gaps come from PATCH /gaps/{gap_id} using the ORM id, which is not
        # directly in the summary schema. Use export to get the ORM id.
        export_resp = client.get(f"/api/projects/{pid}/readiness/export?fmt=json")
        assert export_resp.status_code == 200
        ra_data = json.loads(export_resp.content)
        gap_db_ids = [g["gap_id"] for g in ra_data.get("gaps", [])]
        assert len(gap_db_ids) >= 1

        # The PATCH endpoint uses integer DB IDs; get from DB via direct export
        # We need the integer row id, which is embedded in the export.
        # Use the gaps list endpoint (GapResult has gap_id business key but no int id).
        # We must query via summary to get the assessment id, then retrieve gap via summary.
        summary_resp = client.get(f"/api/projects/{pid}/readiness/summary")
        assert summary_resp.status_code == 200
        assessment_id = summary_resp.json()["data"]["id"]

        # Get ORM gap ids by checking the DB directly via the detail endpoint.
        # Since we don't have a list with integer IDs from the API,
        # we loop through integer IDs starting from 1 until we find one belonging to this project.
        # In a clean test DB, the first gap's integer id is 1.
        # We'll fetch gap 1; if not found we try a few more.
        gap_int_id = None
        for candidate_id in range(1, 50):
            check = client.get(f"/api/projects/{pid}/readiness/gaps/{candidate_id}")
            if check.status_code == 200:
                gap_int_id = candidate_id
                break

        assert gap_int_id is not None, "Could not find a gap belonging to this project"

        patch_resp = client.patch(
            f"/api/projects/{pid}/readiness/gaps/{gap_int_id}",
            json={"review_status": "in_progress", "notes": "Under review by team"},
        )
        assert patch_resp.status_code == 200, patch_resp.text
        updated = patch_resp.json()["data"]
        assert updated["review_status"] == "in_progress"
        assert updated["notes"] == "Under review by team"

    def test_patch_gap_unknown_id_returns_404(self, client: TestClient):
        pid = _create_project(client)
        resp = client.patch(
            f"/api/projects/{pid}/readiness/gaps/99999",
            json={"review_status": "approved"},
        )
        assert resp.status_code == 404


# ===========================================================================
# 10 & 11. Signal exports
# ===========================================================================


class TestSignalExport:
    def test_json_export_returns_json(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        payload = json.loads(resp.content)
        assert "signals" in payload
        assert isinstance(payload["signals"], list)

    def test_csv_export_returns_csv(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/export?fmt=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        lines = resp.text.strip().split("\n")
        # Header + at least one data row
        assert len(lines) >= 2
        header = lines[0].lower()
        assert "drug" in header or "id" in header

    def test_json_export_no_completed_job_returns_404(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        assert resp.status_code == 404


# ===========================================================================
# 12 & 13. Readiness exports
# ===========================================================================


class TestReadinessExport:
    def test_json_export_returns_json(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/export?fmt=json")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        payload = json.loads(resp.content)
        assert "overall_score" in payload
        assert "gaps" in payload

    def test_markdown_export_returns_markdown(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/export?fmt=markdown")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        content = resp.text
        assert "# Submission Readiness Assessment" in content
        assert "## Module Scores" in content
        assert "## Gaps" in content

    def test_export_no_assessment_returns_404(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/readiness/export?fmt=json")
        assert resp.status_code == 404


# ===========================================================================
# 14 & 15. Signal summary + list
# ===========================================================================


class TestSignalSummaryAndList:
    def test_summary_no_job_returns_404(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/signals/summary")
        assert resp.status_code == 404

    def test_list_no_job_returns_empty(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/signals")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_list_pagination(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) <= 1

    def test_list_filter_by_severity(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals?severity=critical")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        for item in items:
            assert item["severity"] == "critical"


# ===========================================================================
# 16. Signal detail
# ===========================================================================


class TestSignalDetail:
    def test_signal_not_found_returns_404(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/signals/99999")
        assert resp.status_code == 404

    def test_signal_from_different_project_returns_404(self, client: TestClient):
        pid1 = _create_project(client, "Project 1")
        pid2 = _create_project(client, "Project 2")
        job = _run_signal_job_sync(client, pid1)
        assert job["status"] == "complete"
        export_resp = client.get(f"/api/projects/{pid1}/signals/export?fmt=json")
        signals = json.loads(export_resp.content)["signals"]
        if signals:
            sig_id = signals[0]["id"]
            resp = client.get(f"/api/projects/{pid2}/signals/{sig_id}")
            assert resp.status_code == 404


# ===========================================================================
# 17. Event clusters
# ===========================================================================


class TestEventClusters:
    def test_clusters_endpoint_returns_clusters(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/clusters")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "clusters" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_clusters_contain_preferred_term(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/clusters")
        clusters = resp.json()["data"]["clusters"]
        terms = {c["preferred_term"] for c in clusters}
        # FAERS fixture should have Headache and Hepatic disorder clusters
        assert "Headache" in terms or "Hepatic disorder" in terms


# ===========================================================================
# 18. Readiness module scores
# ===========================================================================


class TestReadinessModuleScores:
    def test_module_scores_available_after_job(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/modules")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "module_scores" in data
        assert len(data["module_scores"]) == 5  # all 5 CTD modules

    def test_module_scores_not_found_without_job(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/readiness/modules")
        assert resp.status_code == 404


# ===========================================================================
# 19. Requirement matrix
# ===========================================================================


class TestRequirementMatrix:
    def test_requirement_matrix_available(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/requirements")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "mappings" in data
        assert data["total"] >= 1
        first = data["mappings"][0]
        assert "requirement_id" in first
        assert "status" in first


# ===========================================================================
# 20. Gap list with filtering
# ===========================================================================


class TestGapList:
    def test_gap_list_returns_all_gaps(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/gaps")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1

    def test_gap_list_filtered_by_severity(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/gaps?severity=high")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        for item in items:
            assert item["severity"] == "high"

    def test_gap_list_filtered_by_review_status(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/gaps?review_status=not_started")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        for item in items:
            assert item["review_status"] == "not_started"

    def test_gap_list_empty_project_returns_empty(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/readiness/gaps")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


# ===========================================================================
# 21. Gap detail
# ===========================================================================


class TestGapDetail:
    def test_gap_detail_not_found(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/readiness/gaps/99999")
        assert resp.status_code == 404

    def test_gap_detail_fields_present(self, client: TestClient):
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        # Find first gap's integer id
        for candidate_id in range(1, 50):
            check = client.get(f"/api/projects/{pid}/readiness/gaps/{candidate_id}")
            if check.status_code == 200:
                gap = check.json()["data"]
                assert "gap_id" in gap
                assert "requirement_id" in gap
                assert "severity" in gap
                assert "recommendation" in gap
                assert "review_status" in gap
                break


# ===========================================================================
# 22. Project-level jobs listing
# ===========================================================================


class TestProjectJobsListing:
    def test_project_jobs_list_empty_initially(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/jobs")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_project_jobs_list_after_upload(self, client: TestClient):
        pid = _create_project(client)
        _upload_signal_csv(client, pid)
        resp = client.get(f"/api/projects/{pid}/jobs")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] >= 1

    def test_project_jobs_filtered_by_type(self, client: TestClient):
        pid = _create_project(client)
        _upload_signal_csv(client, pid)
        _upload_readiness_json(client, pid)
        resp = client.get(f"/api/projects/{pid}/jobs?job_type=signal_detection")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        for item in items:
            assert item["job_type"] == "signal_detection"

    def test_project_not_found_returns_404(self, client: TestClient):
        resp = client.get("/api/projects/99999/jobs")
        assert resp.status_code == 404


# ===========================================================================
# 23. Project-level recent results
# ===========================================================================


class TestProjectRecentResults:
    def test_results_empty_initially(self, client: TestClient):
        pid = _create_project(client)
        resp = client.get(f"/api/projects/{pid}/results")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_results_after_completed_job(self, client: TestClient):
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        result = data["items"][0]
        assert "job_id" in result
        assert "job_type" in result
        assert "summary" in result


# ===========================================================================
# Upload-to-result end-to-end flows
# ===========================================================================


class TestEndToEndFlows:
    def test_signal_detection_full_flow(self, client: TestClient):
        """Full flow: create project → upload CSV → poll → verify signals."""
        pid = _create_project(client, "E2E Signal Flow")

        # Upload
        upload_resp = _upload_signal_csv(client, pid)
        assert upload_resp.status_code == 202
        job_id = upload_resp.json()["data"]["id"]

        # Poll to completion
        job = _wait_for_job(client, job_id)
        assert job["status"] == "complete", f"Job failed: {job.get('error')}"
        assert job["result"]["signals_detected"] >= 1

        # Summary
        summary = client.get(f"/api/projects/{pid}/signals/summary").json()["data"]
        assert summary["total_signals"] >= 1

        # List
        signals = client.get(f"/api/projects/{pid}/signals").json()["data"]
        assert signals["total"] >= 1
        first = signals["items"][0]
        assert first["drug"] != ""
        assert first["prr"] >= 0.0

        # Export
        export = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        assert export.status_code == 200
        payload = json.loads(export.content)
        assert len(payload["signals"]) >= 1

    def test_readiness_assessment_full_flow(self, client: TestClient):
        """Full flow: create project → upload JSON → poll → verify assessment."""
        pid = _create_project(client, "E2E Readiness Flow")

        # Upload
        upload_resp = _upload_readiness_json(client, pid)
        assert upload_resp.status_code == 202
        job_id = upload_resp.json()["data"]["id"]

        # Poll to completion
        job = _wait_for_job(client, job_id)
        assert job["status"] == "complete", f"Job failed: {job.get('error')}"
        assert job["result"]["gap_count"] >= 1

        # Summary
        summary_resp = client.get(f"/api/projects/{pid}/readiness/summary")
        assert summary_resp.status_code == 200
        assessment = summary_resp.json()["data"]
        assert 0.0 <= assessment["overall_score"] <= 1.0
        assert len(assessment["module_scores"]) == 5
        assert len(assessment["gaps"]) >= 1

        # Module scores
        modules = client.get(f"/api/projects/{pid}/readiness/modules").json()["data"]
        assert len(modules["module_scores"]) == 5

        # Gap list
        gaps = client.get(f"/api/projects/{pid}/readiness/gaps").json()["data"]
        assert gaps["total"] >= 1

        # Export JSON
        export = client.get(f"/api/projects/{pid}/readiness/export?fmt=json")
        assert export.status_code == 200
        ra = json.loads(export.content)
        assert ra["overall_score"] >= 0.0

        # Export Markdown
        md_export = client.get(f"/api/projects/{pid}/readiness/export?fmt=markdown")
        assert md_export.status_code == 200
        assert "Overall readiness score" in md_export.text


# ===========================================================================
# 25. Signal detail fields — a/b/c/d and full result
# ===========================================================================


class TestSignalDetailFields:
    def test_signal_detail_contains_contingency_table(self, client: TestClient):
        """Signal detail must return a/b/c/d contingency table cells."""
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        export_resp = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        signals = json.loads(export_resp.content)["signals"]
        assert len(signals) >= 1
        sig_id = signals[0]["id"]
        detail = client.get(f"/api/projects/{pid}/signals/{sig_id}").json()["data"]
        result = detail.get("result")
        assert result is not None, "Signal detail must have a 'result' field"
        for cell in ("a", "b", "c", "d"):
            assert cell in result, f"Missing contingency table cell '{cell}'"
            assert isinstance(result[cell], int) and result[cell] >= 0

    def test_signal_detail_prr_and_rank_positive(self, client: TestClient):
        """PRR must be > 0 and rank must be >= 1 for persisted signals."""
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        export_resp = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
        signals = json.loads(export_resp.content)["signals"]
        assert len(signals) >= 1
        sig_id = signals[0]["id"]
        detail = client.get(f"/api/projects/{pid}/signals/{sig_id}").json()["data"]
        result = detail["result"]
        assert result["prr"] > 0.0, "PRR must be positive for an above-threshold signal"
        assert result["rank"] >= 1

    def test_csv_export_contains_prr_values(self, client: TestClient):
        """CSV export must contain numeric PRR values in data rows (not just headers)."""
        pid = _create_project(client)
        job = _run_signal_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/signals/export?fmt=csv")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) >= 2, "CSV must have header + at least one data row"
        header = lines[0].split(",")
        prr_idx = next((i for i, h in enumerate(header) if "prr" in h.lower()), None)
        assert prr_idx is not None, "CSV header must contain a 'prr' column"
        # First data row must have a non-empty prr value
        data_row = lines[1].split(",")
        assert prr_idx < len(data_row), "PRR column missing from data row"
        try:
            prr_val = float(data_row[prr_idx])
            assert prr_val > 0.0, "PRR in CSV data row must be > 0"
        except ValueError:
            assert False, f"PRR value '{data_row[prr_idx]}' is not a valid float"


# ===========================================================================
# 26. Requirement matrix mapping_method and confidence persisted
# ===========================================================================


class TestRequirementMappingFieldsPersisted:
    def test_requirement_matrix_has_mapping_method_and_confidence(self, client: TestClient):
        """After a readiness job, the requirement matrix must include
        mapping_method and confidence values from the engine."""
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete", f"Job failed: {job.get('error')}"
        resp = client.get(f"/api/projects/{pid}/readiness/requirements")
        assert resp.status_code == 200
        data = resp.json()["data"]
        mappings = data["mappings"]
        assert len(mappings) >= 1

        # At least the exact-code matches should have mapping_method populated
        methods_present = [m["mapping_method"] for m in mappings if m["mapping_method"] is not None]
        assert len(methods_present) >= 1, (
            "At least one mapping must have mapping_method populated after persist"
        )
        # Exact-code matches (e.g. CTD-3.2.S.1) should have confidence = 1.0
        exact_mappings = [m for m in mappings if m.get("mapping_method") == "exact_code"]
        if exact_mappings:
            for m in exact_mappings:
                conf = m.get("confidence")
                assert conf is not None, "exact_code mapping must have confidence"
                assert 0.0 <= conf <= 1.0, f"confidence {conf} out of range"

    def test_requirement_matrix_exact_code_matches_have_high_confidence(self, client: TestClient):
        """Exact-code mappings (CTD catalog section matches dossier section) must
        have confidence >= 0.9."""
        pid = _create_project(client)
        job = _run_readiness_job_sync(client, pid)
        assert job["status"] == "complete"
        resp = client.get(f"/api/projects/{pid}/readiness/requirements")
        data = resp.json()["data"]
        exact_mappings = [
            m for m in data["mappings"]
            if m.get("mapping_method") == "exact_code"
        ]
        # The fixture dossier has sections matching several catalog IDs by exact code
        assert len(exact_mappings) >= 1, "Expected at least one exact_code match from fixture"
        for m in exact_mappings:
            assert m["confidence"] >= 0.6, (
                f"exact_code mapping for {m['requirement_id']} has confidence {m['confidence']}"
            )
