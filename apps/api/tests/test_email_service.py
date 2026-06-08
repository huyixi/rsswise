import smtplib

import pytest

from app.core.config import settings
from app.services.email_service import (
    EmailAttachment,
    SMTPConfigError,
    build_email_message,
    translate_smtp_config_error,
    translate_smtp_error,
)


def test_build_email_message_includes_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from_email", "rsswise@example.com")

    message = build_email_message(
        subject="RSSWise 文章推送 - 2026-06-04",
        to_email="reader@example.com",
        text_body="本次推送包含 1 篇文章。",
        attachments=[
            EmailAttachment(
                filename="rsswise-digest-2026-06-04.epub",
                content=b"epub-bytes",
                content_type="application/epub+zip",
            )
        ],
    )

    assert message["Subject"] == "RSSWise 文章推送 - 2026-06-04"
    assert message["To"] == "reader@example.com"
    assert message.is_multipart()


def test_validate_smtp_config_rejects_missing_host() -> None:
    from app.services.email_service import validate_smtp_config

    with pytest.raises(SMTPConfigError):
        validate_smtp_config(
            smtp_host="",
            smtp_from_email="rsswise@example.com",
        )
