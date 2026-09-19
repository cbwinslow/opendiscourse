from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    # Primary runtime: local peer-authenticated PostgreSQL 17 on the bare-metal
    # service. Docker remains an optional development fallback only.
    database_url: str = "postgresql:///opendiscourse?port=5434"
    census_api_key: str | None = None
    fred_api_key: str | None = None
    congress_api_key: str | None = None
    # Optional: BLS API v2 works unregistered at a lower daily rate limit.
    bls_api_key: str | None = None
    # Raw artifacts belong on the large workspace partition, not alongside the
    # application checkout or Docker's default root-disk volume.
    data_root: str = "./data-lake/opendiscourse/raw"
    # Optional roots for data downloaded before this project managed its lake.
    # Unset on a fresh install; see inventory/lake_layout.yaml for what is
    # expected under each. Set via LEGACY_LAKE_ROOT / LEGACY_PROJECT_ROOT.
    legacy_lake_root: str | None = None
    legacy_project_root: str | None = None

    @field_validator("data_root", "legacy_lake_root", "legacy_project_root", mode="after")
    @classmethod
    def _anchor_to_project(cls, value: str | None) -> str | None:
        """Resolve relative paths against the project root, not the caller's cwd.

        Without this the lake silently forked whenever a command ran from a
        different directory.
        """
        if value is None:
            return None
        path = Path(value).expanduser()
        return str(path if path.is_absolute() else PROJECT_ROOT / path)


settings = Settings()
