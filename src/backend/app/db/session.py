"""SQLModel / SQLite engine and session factory."""
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

# connect_args required for SQLite to work across threads in FastAPI
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.app_env == "development",
)


def create_db_and_tables() -> None:
    """Create all tables. Called once at startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
