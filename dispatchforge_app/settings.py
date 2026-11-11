"""Runtime configuration. Production requires an explicit secret and database."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    secret: str
    database_url: str

    @property
    def production(self) -> bool:
        return self.environment == "production"


def load_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    secret = os.getenv("APP_SECRET", "development-only-unsafe-secret-do-not-deploy")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./dispatchforge_dev.sqlite3")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    if environment == "production":
        if len(secret) < 32 or secret == "development-only-unsafe-secret-do-not-deploy":
            raise RuntimeError("APP_SECRET of 32+ unpredictable characters is required in production")
        if not database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Production requires persistent PostgreSQL via DATABASE_URL")
    return Settings(environment, secret, database_url)
