import os
from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.getenv("DB_PATH", "/data/finanztracker.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def _run_migrations() -> None:
    """Idempotente Schema-Migrationen für bestehende DBs."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE transaction ADD COLUMN account_id INTEGER"))
            conn.commit()
        except Exception:
            pass  # Spalte existiert bereits


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
