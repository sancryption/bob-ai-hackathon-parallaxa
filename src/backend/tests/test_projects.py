"""Tests for project CRUD endpoints."""
from fastapi.testclient import TestClient


def test_create_project(client: TestClient):
    response = client.post(
        "/api/projects",
        json={"name": "Test Project", "description": "A test project"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["name"] == "Test Project"
    assert body["data"]["status"] == "draft"
    assert "id" in body["data"]


def test_list_projects_empty(client: TestClient):
    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_list_projects(client: TestClient):
    client.post("/api/projects", json={"name": "Project A"})
    client.post("/api/projects", json={"name": "Project B"})
    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 2
    assert len(body["data"]["items"]) == 2


def test_get_project(client: TestClient):
    create_resp = client.post("/api/projects", json={"name": "My Project"})
    project_id = create_resp.json()["data"]["id"]

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == project_id


def test_get_project_not_found(client: TestClient):
    response = client.get("/api/projects/99999")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


def test_create_project_missing_name(client: TestClient):
    response = client.post("/api/projects", json={"description": "No name"})
    assert response.status_code == 422
