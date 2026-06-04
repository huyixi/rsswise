from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models import Session, User


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: DbSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    session = db.execute(
        select(Session)
        .where(Session.token_hash == hash_session_token(session_token))
        .options(joinedload(Session.user))
    ).scalar_one_or_none()
    if session is None or session.expires_at <= datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    return session.user
