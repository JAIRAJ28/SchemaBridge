from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SchemaBridge"
    app_environment: str = "development"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCHEMABRIDGE_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()