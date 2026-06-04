import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reads_explicit_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        app_env="development",
        log_level="INFO",
        deepseek_api_key="",
    )

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url == "redis://127.0.0.1:6379/0"


def test_settings_ignores_frontend_and_compose_only_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        VITE_API_BASE_URL="/api",
        POSTGRES_PASSWORD="secret",
        NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000",
    )

    assert not hasattr(settings, "VITE_API_BASE_URL")
    assert not hasattr(settings, "POSTGRES_PASSWORD")
    assert not hasattr(settings, "NEXT_PUBLIC_API_BASE_URL")


def test_settings_reads_smtp_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="rsswise@example.com",
        smtp_password="secret",
        smtp_from_email="rsswise@example.com",
        smtp_from_name="RSSWise",
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_timeout_seconds=20,
        email_digest_default_interval_days=1,
        email_digest_default_send_time="08:00",
    )

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 587
    assert settings.smtp_user == "rsswise@example.com"
    assert settings.smtp_password == "secret"
    assert settings.smtp_from_email == "rsswise@example.com"
    assert settings.smtp_from_name == "RSSWise"
    assert settings.smtp_use_tls is True
    assert settings.smtp_use_ssl is False
    assert settings.smtp_timeout_seconds == 20
    assert settings.email_digest_default_interval_days == 1
    assert settings.email_digest_default_send_time == "08:00"


def test_settings_rejects_simultaneous_smtp_tls_and_ssl() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
            redis_url="redis://127.0.0.1:6379/0",
            smtp_use_tls=True,
            smtp_use_ssl=True,
        )


def test_settings_rejects_invalid_default_digest_interval() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
            redis_url="redis://127.0.0.1:6379/0",
            email_digest_default_interval_days=0,
        )
