from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: SecretStr = SecretStr("")
    jwt_secret: SecretStr = SecretStr("")
    mfa_encryption_key: SecretStr | None = None
    jwt_issuer: str = "aquabloom"
    access_token_minutes: int = 20
    refresh_token_days: int = 7
    allow_registration: bool = False
    cors_origins: str = "http://localhost:5173"
    storage_root: Path = Path("/app/data")
    satellite_service_url: str = "http://satellite-kuberoapp:80"
    scientific_service_url: str = "http://scientific-kuberoapp:80"
    internal_service_token: SecretStr | None = None
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: SecretStr | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
