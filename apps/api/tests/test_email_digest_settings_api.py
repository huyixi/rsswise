from collections.abc import Iterator
import smtplib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base, EmailDigestSetting
from app.schemas import EmailDigestSettingsUpdate
from app.services.email_service import SMTPConfigError


def test_email_digest_setting_model_exists() -> None:
    assert EmailDigestSetting.__tablename__ == "email_digest_settings"


def test_email_digest_update_accepts_hh_mm_time() -> None:
    payload = EmailDigestSettingsUpdate(
        recipient_email="reader@example.com",
        enabled=True,
        send_interval_days=7,
        send_time="07:30",
    )

    assert payload.recipient_email == "reader@example.com"
    assert payload.enabled is True
    assert payload.send_interval_days == 7
    assert payload.send_time == "07:30"


def test_email_digest_update_rejects_enabled_without_email() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="",
            enabled=True,
            send_interval_days=1,
            send_time="08:00",
        )


def test_email_digest_update_rejects_invalid_send_time() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="reader@example.com",
            enabled=True,
            send_interval_days=1,
            send_time="24:00",
        )


def test_email_digest_update_rejects_invalid_send_interval() -> None:
    with pytest.raises(ValidationError):
        EmailDigestSettingsUpdate(
            recipient_email="reader@example.com",
            enabled=True,
            send_interval_days=0,
            send_time="08:00",
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    response = client.post(
        "/auth/register",
        json={"email": "reader@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    return client


def test_email_digest_settings_requires_authentication(client: TestClient) -> None:
    assert client.get("/settings/email-digest").status_code == 401
    assert client.put("/settings/email-digest", json={}).status_code == 401
    assert client.post("/settings/email-digest/test").status_code == 401


def test_get_email_digest_settings_returns_default(authenticated_client: TestClient) -> None:
    client = authenticated_client
    response = client.get("/settings/email-digest")

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] is None
    assert data["enabled"] is False
    assert data["send_interval_days"] == 1
    assert data["send_time"] == "08:00"
    assert data["timezone"] == "Asia/Shanghai"


def test_put_email_digest_settings_updates_values(authenticated_client: TestClient) -> None:
    client = authenticated_client
    response = client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 7,
            "send_time": "07:30",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] == "reader@example.com"
    assert data["enabled"] is True
    assert data["send_interval_days"] == 7
    assert data["send_time"] == "07:30"


def test_put_email_digest_settings_rejects_enabled_without_email(
    authenticated_client: TestClient,
) -> None:
    client = authenticated_client
    response = client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    assert response.status_code == 422


def test_post_email_digest_test_rejects_missing_recipient(
    authenticated_client: TestClient,
) -> None:
    client = authenticated_client
    response = client.post("/settings/email-digest/test")

    assert response.status_code == 400
    assert response.json()["detail"] == "recipient email is not configured"


def test_post_email_digest_test_sends_to_saved_recipient(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = authenticated_client
    client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )
    sent_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.routers.settings.send_email",
        lambda **kwargs: sent_messages.append(kwargs),
    )

    response = client.post("/settings/email-digest/test")

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    assert sent_messages[0]["to_email"] == "reader@example.com"


def test_post_email_digest_test_translates_smtp_auth_error(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = authenticated_client
    client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    def _raise_auth_error(**kwargs: object) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")

    monkeypatch.setattr("app.routers.settings.send_email", _raise_auth_error)

    response = client.post("/settings/email-digest/test")

    assert response.status_code == 502
    assert "认证失败" in response.json()["detail"]


def test_post_email_digest_test_translates_connection_refused(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = authenticated_client
    client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    def _raise_connection_refused(**kwargs: object) -> None:
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(
        "app.routers.settings.send_email", _raise_connection_refused
    )

    response = client.post("/settings/email-digest/test")

    assert response.status_code == 502
    assert "无法连接" in response.json()["detail"]


def test_post_email_digest_test_translates_timeout(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = authenticated_client
    client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    def _raise_timeout(**kwargs: object) -> None:
        raise TimeoutError("connection timed out")

    monkeypatch.setattr("app.routers.settings.send_email", _raise_timeout)

    response = client.post("/settings/email-digest/test")

    assert response.status_code == 502
    assert "超时" in response.json()["detail"]


def test_post_email_digest_test_translates_smtp_config_error(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = authenticated_client
    client.put(
        "/settings/email-digest",
        json={
            "recipient_email": "reader@example.com",
            "enabled": True,
            "send_interval_days": 1,
            "send_time": "08:00",
        },
    )

    monkeypatch.setattr(
        "app.services.email_service.settings.smtp_host", ""
    )

    def _raise_config_error(**kwargs: object) -> None:
        raise SMTPConfigError("SMTP_HOST is required")

    monkeypatch.setattr("app.routers.settings.send_email", _raise_config_error)

    response = client.post("/settings/email-digest/test")

    assert response.status_code == 400
    assert "服务器地址" in response.json()["detail"]
