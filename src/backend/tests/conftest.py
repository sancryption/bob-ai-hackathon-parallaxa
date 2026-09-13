"""Pytest configuration — in-memory SQLite for all tests."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, StaticPool

from app.db.session import get_session
from app.main import create_app
from app.services import job_runner


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session, engine):
    app = create_app()

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    # Point the background job runner at the same in-memory engine
    job_runner.set_engine_factory(lambda: engine)

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    job_runner.set_engine_factory(None)
