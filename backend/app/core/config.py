from functools import cached_property
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return (
        len(normalized) < 8
        or "..." in normalized
        or normalized.startswith(("replace", "changeme", "your-", "example"))
    )


class Settings(BaseSettings):
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"

    database_url: str | None = None
    database_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_USER", "user"),
    )
    database_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_PASSWORD", "password"),
    )
    database_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_HOST", "host"),
    )
    database_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("DATABASE_PORT", "port"),
    )
    database_name: str = Field(
        default="postgres",
        validation_alias=AliasChoices("DATABASE_NAME", "dbname"),
    )

    mistral_api_key: str | None = None
    mistral_extract_model: str = "mistral-small-latest"
    mistral_transform_model: str = "mistral-large-latest"
    mistral_embed_model: str = "mistral-embed"
    mistral_atlassian_connector_id: str | None = None
    mistral_api_base_url: str = "https://api.mistral.ai"

    atlassian_base_url: str | None = None
    atlassian_email: str | None = None
    atlassian_api_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if not _is_placeholder(self.database_url):
            url = make_url(self.database_url)
            if url.drivername == "postgresql":
                url = url.set(drivername="postgresql+psycopg")
            if not url.query.get("sslmode"):
                url = url.update_query_dict({"sslmode": "require"})
            self.database_url = url.render_as_string(hide_password=False)
            return self

        split_values = (
            self.database_user,
            self.database_password,
            self.database_host,
            self.database_name,
        )
        if any(_is_placeholder(value) for value in split_values):
            raise ValueError(
                "Set a valid DATABASE_URL, or provide user, password, host, port, "
                "and dbname in .env. Placeholder values are not accepted."
            )

        self.database_url = URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"sslmode": "require"},
        ).render_as_string(hide_password=False)
        return self

    @cached_property
    def has_mistral_key(self) -> bool:
        return not _is_placeholder(self.mistral_api_key)


settings = Settings()
