import os
from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The checkout that holds inventory/, .env and relative paths. Override with
# OPENDISCOURSE_HOME when the package is not run from its source checkout.
PROJECT_ROOT = Path(os.environ.get("OPENDISCOURSE_HOME") or Path(__file__).resolve().parents[2])


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

    @field_validator("data_root", mode="after")
    @classmethod
    def _anchor_data_root(cls, value: str, info: ValidationInfo) -> str:
        """Resolve a relative DATA_ROOT against the project root, not the caller's cwd.

        Without this the download folder silently forked whenever a command ran
        from a different directory. A blank value is an error, never the checkout.
        """
        if not value.strip():
            raise ValueError("DATA_ROOT must not be empty")
        try:
            path = Path(value.strip()).expanduser()
        except RuntimeError as exc:  # ~unknownuser
            raise ValueError(f"cannot expand DATA_ROOT {value!r}: {exc}") from exc
        return str(path if path.is_absolute() else PROJECT_ROOT / path)


settings = Settings()
