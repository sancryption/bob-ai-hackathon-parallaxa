"""Manual end-to-end flow validation for SafetyReady."""
import io, json, pathlib, time
from sqlmodel import SQLModel, Session, create_engine, StaticPool
from fastapi.testclient import TestClient
from app.main import create_app
from app.db.session import get_session
from app.services import job_runner

print("=== SafetyReady Manual Flow Validation ===")
print()

# Shared in-memory DB
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SQLModel.metadata.create_all(engine)

app = create_app()

def override_get_session():
    with Session(engine) as s:
        yield s

app.dependency_overrides[get_session] = override_get_session
job_runner.set_engine_factory(lambda: engine)
client = TestClient(app)


def wait_for_job(job_id, max_seconds=15.0):
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        data = r.json()["data"]
        if data["status"] in ("complete", "failed"):
            return data
        time.sleep(0.05)
    return client.get(f"/api/jobs/{job_id}").json()["data"]


# ---- FLOW 1: Signal Detection ----
print("--- FLOW 1: Signal Detection ---")
r = client.post("/api/projects", json={"name": "Signal Demo"})
pid = r.json()["data"]["id"]
print(f"  Created project id={pid}")

csv_text = pathlib.Path("tests/fixtures/faers_demo.csv").read_text(encoding="utf-8")
r2 = client.post(
    f"/api/projects/{pid}/signals/upload",
    files={"file": ("faers_demo.csv", io.BytesIO(csv_text.encode()), "text/csv")},
)
assert r2.status_code == 202, r2.text
job_id = r2.json()["data"]["id"]
print(f"  Upload accepted -> job_id={job_id}")

job = wait_for_job(job_id)
assert job["status"] == "complete", f"FAILED: {job.get('error')}"
print(f"  Job status: {job['status']}")
print(f"  Result: signals_detected={job['result']['signals_detected']}, pairs_above={job['result']['pairs_above_threshold']}")

summary = client.get(f"/api/projects/{pid}/signals/summary").json()["data"]
print(f"  Summary: total={summary['total_signals']}, above_threshold={summary['signals_above_threshold']}")

signals = client.get(f"/api/projects/{pid}/signals").json()["data"]
print(f"  Signal list: {signals['total']} total")
if signals["items"]:
    first = signals["items"][0]
    print(f"  Top signal: {first['drug']} / {first['event']}, PRR={first['prr']:.2f}, severity={first['severity']}")

clusters = client.get(f"/api/projects/{pid}/signals/clusters").json()["data"]
print(f"  Clusters: {clusters['total']} event clusters")

export_json = client.get(f"/api/projects/{pid}/signals/export?fmt=json")
assert export_json.status_code == 200
payload = json.loads(export_json.content)
print(f"  JSON export: {len(payload['signals'])} signals")

export_csv = client.get(f"/api/projects/{pid}/signals/export?fmt=csv")
assert export_csv.status_code == 200
csv_lines = export_csv.text.strip().split("\n")
print(f"  CSV export: {len(csv_lines)-1} data rows")

print()

# ---- FLOW 2: Readiness Assessment ----
print("--- FLOW 2: Submission Readiness ---")
r9 = client.post("/api/projects", json={"name": "Readiness Demo"})
pid2 = r9.json()["data"]["id"]
print(f"  Created project id={pid2}")

json_text = pathlib.Path("tests/fixtures/dossier_outline.json").read_text(encoding="utf-8")
r10 = client.post(
    f"/api/projects/{pid2}/readiness/upload",
    files={"file": ("dossier_outline.json", io.BytesIO(json_text.encode()), "application/json")},
)
assert r10.status_code == 202, r10.text
job_id2 = r10.json()["data"]["id"]
print(f"  Upload accepted -> job_id={job_id2}")

job2 = wait_for_job(job_id2)
assert job2["status"] == "complete", f"FAILED: {job2.get('error')}"
print(f"  Job status: {job2['status']}")
print(f"  Result: overall_score={job2['result']['overall_score']:.3f}, gaps={job2['result']['gap_count']}")

summary2 = client.get(f"/api/projects/{pid2}/readiness/summary").json()["data"]
print(f"  Assessment: overall_score={summary2['overall_score']:.3f}")
print(f"  Module scores: {[m['module'] for m in summary2['module_scores']]}")

high_gaps = [g for g in summary2["gaps"] if g["severity"] == "high"]
print(f"  High-severity gaps: {[g['requirement_id'] for g in high_gaps[:4]]}")

gaps = client.get(f"/api/projects/{pid2}/readiness/gaps").json()["data"]
print(f"  Gaps list: {gaps['total']} total")

modules = client.get(f"/api/projects/{pid2}/readiness/modules").json()["data"]
print(f"  Module scores: {len(modules['module_scores'])} modules")

requirements = client.get(f"/api/projects/{pid2}/readiness/requirements").json()["data"]
print(f"  Requirements matrix: {requirements['total']} mappings")

# Gap review update
for candidate_id in range(1, 50):
    check = client.get(f"/api/projects/{pid2}/readiness/gaps/{candidate_id}")
    if check.status_code == 200:
        gap_int_id = candidate_id
        break

patch = client.patch(
    f"/api/projects/{pid2}/readiness/gaps/{gap_int_id}",
    json={"review_status": "in_progress", "notes": "Reviewed in manual flow"},
)
assert patch.status_code == 200
print(f"  Gap review update: gap_id={gap_int_id}, new_status={patch.json()['data']['review_status']}")

export_json2 = client.get(f"/api/projects/{pid2}/readiness/export?fmt=json")
assert export_json2.status_code == 200
ra = json.loads(export_json2.content)
print(f"  JSON export: overall_score={ra['overall_score']:.3f}, {len(ra['gaps'])} gaps")

export_md = client.get(f"/api/projects/{pid2}/readiness/export?fmt=markdown")
assert export_md.status_code == 200
assert "# Submission Readiness Assessment" in export_md.text
print(f"  Markdown export: {len(export_md.text.split(chr(10)))} lines")

results = client.get(f"/api/projects/{pid2}/results").json()["data"]
print(f"  Project results: {results['total']} completed jobs")

print()
print("=== All manual flows completed successfully ===")
