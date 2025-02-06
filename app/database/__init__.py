import os

DB_BACKEND = os.getenv("MARBLE_API_DB_BACKEND", "sqlite")

if DB_BACKEND == "sqlite":
    from app.database.sqlite import SessionDep, on_start
else:
    raise RuntimeError(f"Database backend '{DB_BACKEND}' is not supported.")

__all__ = ["SessionDep", "on_start"]
