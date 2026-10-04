from functools import lru_cache
from typing import Literal

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SchemaBridge"
    app_version: str = "1.0.0"
    app_environment: Literal[
        "development",
        "test",
        "staging",
        "production",
    ] = "development"
    api_prefix: str = "/api/v1"

    max_upload_bytes: int = Field(
        default=20 * 1024 * 1024,
        gt=0,
    )
    max_record_count: int = Field(
        default=10_000,
        gt=0,
    )
    max_schema_fields: int = Field(
        default=200,
        gt=0,
    )
    max_record_fields: int = Field(
        default=200,
        gt=0,
    )
    max_record_bytes: int = Field(
        default=256 * 1024,
        gt=0,
    )
    max_string_length: int = Field(
        default=100_000,
        gt=0,
    )

    default_page_size: int = Field(
        default=50,
        gt=0,
    )
    max_page_size: int = Field(
        default=200,
        gt=0,
    )
    profile_distinct_value_limit: int = Field(
        default=100,
        gt=0,
    )
    storage_root: str = "data/uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCHEMABRIDGE_",
        case_sensitive=False,
        extra="ignore",
    )
    database_url: SecretStr
    database_pool_size: int = Field(
        default=5,
        ge=1,
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
    )
    database_pool_timeout_seconds: int = Field(
        default=30,
        ge=1,
    )
    database_connect_timeout_seconds: int = Field(
        default=10,
        ge=1,
    )
    database_pool_recycle_seconds: int = Field(
        default=1800,
        ge=60,
    )

    @model_validator(mode="after")
    def validate_related_settings(self) -> "Settings":
        if self.default_page_size > self.max_page_size:
            raise ValueError(
                "default_page_size cannot exceed max_page_size."
            )

        if self.max_record_bytes > self.max_upload_bytes:
            raise ValueError(
                "max_record_bytes cannot exceed max_upload_bytes."
            )

        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        database_url = value.get_secret_value()

        if not database_url:
            raise ValueError("database_url cannot be empty.")

        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError(
                "database_url must use PostgreSQL with Psycopg."
            )

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
