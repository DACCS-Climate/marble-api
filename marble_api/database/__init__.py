import os

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


class Client(AsyncMongoClient):
    """AsyncMongoClient with different defaults."""

    def get_default_database(self, default: str | None = "marble-api", **kwargs) -> AsyncDatabase:
        """Override AsyncMongoClient.default_get_database but with a specific default."""
        return super().get_default_database(default, **kwargs)

    @property
    def db(self) -> AsyncDatabase:
        """Shortcut to get_default_database."""
        return self.get_default_database()


client = Client(os.environ["MONGODB_URI"], tz_aware=True)
