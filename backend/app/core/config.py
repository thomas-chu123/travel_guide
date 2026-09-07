from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    allowed_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="ALLOWED_ORIGINS",
    )
    database_url: str = "sqlite:///./data/tokyo_event_map.db"
    map_style_url: str | None = None
    pmtiles_url: str | None = None
    valhalla_url: str = "http://localhost:8002"
    searxng_url: str | None = None
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    google_maps_api_key: str | None = None
    supabase_public_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_admin_token: str | None = None
    supabase_allowed_tables_raw: str = Field(default="", validation_alias="SUPABASE_ALLOWED_TABLES")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def supabase_allowed_tables(self) -> set[str]:
        return {
            table.strip()
            for table in self.supabase_allowed_tables_raw.split(",")
            if table.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
