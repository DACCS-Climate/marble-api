from collections.abc import Callable

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from marble_api._config import config


class Client(AsyncMongoClient):
    """AsyncMongoClient with different defaults."""

    def get_default_database(self, default: str | None = "marble-api", **kwargs) -> AsyncDatabase:
        """Override AsyncMongoClient.default_get_database but with a specific default."""
        return super().get_default_database(default, **kwargs)

    @property
    def db(self) -> AsyncDatabase:
        """Shortcut to get_default_database."""
        return self.get_default_database()


client = Client(str(config.mongodb_uri), tz_aware=True)


def collection(name: str) -> Callable:
    """
    Return a function that returns the named mongodb collection.

    Using this ensures that a new collection object is created when needed instead
    of creating a collection once when the module is loaded (which may drop connection
    to the database if the mongodb instance goes offline temporarily.)
    """

    def _(name: str = name) -> AsyncCollection:
        return client.db[name]

    return _
