"""SQLModel / SQLite engine and session factory."""
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings
import app.models  # noqa: F401 — registers all ORM models with SQLModel.metadata

# connect_args required for SQLite to work across threads in FastAPI
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.app_env == "development",
)


def _apply_migrations(conn) -> None:
    """Idempotent column migrations for databases created before the current schema.

    SQLite's CREATE TABLE IF NOT EXISTS does not add columns to existing tables,
    so any DB created from an older schema version will be missing columns added
    later.  ALTER TABLE … ADD COLUMN is safe to retry — we catch the OperationalError
    that SQLite raises when the column already exists.
    """
    migrations = [
        "ALTER TABLE requirement_mappings ADD COLUMN mapping_method VARCHAR(64)",
        "ALTER TABLE requirement_mappings ADD COLUMN confidence REAL",
    ]
    cur = conn.cursor()
    for sql in migrations:
        try:
            cur.execute(sql)
        except Exception:
            pass  # column already exists — safe to ignore
    conn.commit()


def create_db_and_tables() -> None:
    """Create all tables then apply any pending schema migrations."""
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        _apply_migrations(conn.connection.dbapi_connection)


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
