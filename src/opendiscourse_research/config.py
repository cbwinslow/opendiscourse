from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Primary runtime: local peer-authenticated PostgreSQL 17 on the bare-metal
    # service. Docker remains an optional development fallback only.
    database_url: str = "postgresql:///opendiscourse?port=5434"
    census_api_key: str | None = None
    fred_api_key: str | None = None
    congress_api_key: str | None = None
    # Raw artifacts belong on the large workspace partition, not alongside the
    # application checkout or Docker's default root-disk volume.
    data_root: str = "/home/cbwinslow/workspace/data-lake/opendiscourse/raw"


settings = Settings()
