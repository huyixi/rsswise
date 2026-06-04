from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from app.core.config import settings


class SMTPConfigError(ValueError):
    pass


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str


def validate_smtp_config(
    *,
    smtp_host: str | None = None,
    smtp_from_email: str | None = None,
) -> None:
    host = settings.smtp_host if smtp_host is None else smtp_host
    from_email = settings.smtp_from_email if smtp_from_email is None else smtp_from_email
    if not host:
        raise SMTPConfigError("SMTP_HOST is required")
    if not from_email:
        raise SMTPConfigError("SMTP_FROM_EMAIL is required")


def build_email_message(
    *,
    subject: str,
    to_email: str,
    text_body: str,
    attachments: list[EmailAttachment] | None = None,
) -> EmailMessage:
    validate_smtp_config()

    message = EmailMessage()
    from_display = settings.smtp_from_email
    if settings.smtp_from_name:
        from_display = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["From"] = from_display
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)

    for attachment in attachments or []:
        maintype, subtype = attachment.content_type.split("/", 1)
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return message


def send_email(
    *,
    subject: str,
    to_email: str,
    text_body: str,
    attachments: list[EmailAttachment] | None = None,
) -> None:
    message = build_email_message(
        subject=subject,
        to_email=to_email,
        text_body=text_body,
        attachments=attachments,
    )

    smtp_cls = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_cls(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as smtp:
        smtp.ehlo()
        if settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
