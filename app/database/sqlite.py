import os
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

if TYPE_CHECKING:
    from typing import Iterable

sqlite_file_name = os.getenv("MARBLE_API_SQLITE_DB_FILE", "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def on_start() -> None:
    """Run when the app starts to initialize the database."""
    SQLModel.metadata.create_all(engine)


def _get_session() -> "Iterable[Session]":
    """Yield the database session."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(_get_session)]
