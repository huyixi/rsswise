from app.core.config import Settings


def test_settings_reads_explicit_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
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
