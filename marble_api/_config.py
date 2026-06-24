from typing import Self

from pydantic import HttpUrl, MongoDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    mongodb_uri: MongoDsn
    magpie_auth_enabled: bool = True
    magpie_url: HttpUrl | None = None
    magpie_admin_group: str = "administrators"

    model_config = SettingsConfigDict(env_prefix="marble_api_")

    @model_validator(mode="after")
    def require_auth_settings(self) -> Self:
        if self.magpie_auth_enabled:
            not_set = [field for field, value in self if field.startswith("magpie_") and not value]
            if not_set:
                raise ValueError(f"The following fields are required if 'magpie_auth_enabled' is set: {not_set}")
        return self


config = Config()
