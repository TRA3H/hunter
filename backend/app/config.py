from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://hunter:hunter_secret_change_me@localhost:5432/hunter"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-this-to-a-random-secret-key"

    # CORS
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Email - Resend
    resend_api_key: str = ""
    notification_from_email: str = "hunter@yourdomain.com"
    notification_to_email: str = ""

    # Email - SMTP fallback
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # Logging
    log_level: str = "INFO"

    # Playwright
    playwright_headless: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
