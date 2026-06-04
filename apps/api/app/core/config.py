from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str
    redis_url: str

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"

    session_cookie_name: str = "rsswise_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    session_cookie_secure: bool = False
    initial_user_email: str = ""
    initial_user_password: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "RSSWise"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 20

    email_digest_default_interval_days: int = 1
    email_digest_default_send_time: str = "08:00"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_smtp_security(self) -> Self:
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true")
        if (
            self.email_digest_default_interval_days < 1
            or self.email_digest_default_interval_days > 30
        ):
            raise ValueError("EMAIL_DIGEST_DEFAULT_INTERVAL_DAYS must be between 1 and 30")
        return self


settings = Settings()
