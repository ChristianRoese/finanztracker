import os
from collections.abc import Generator

from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.getenv("DB_PATH", "/data/finanztracker.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
