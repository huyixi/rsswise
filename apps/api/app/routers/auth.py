from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import Session, User
from app.schemas import AuthRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def create_session(db: DbSession, user: User) -> str:
    token = generate_session_token()
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=settings.session_max_age_seconds),
        )
    )
    return token


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRequest, response: Response, db: DbSession = Depends(get_db)):
    email = normalize_email(str(payload.email))
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    token = create_session(db, user)
    db.commit()
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: AuthRequest, response: Response, db: DbSession = Depends(get_db)):
    email = normalize_email(str(payload.email))
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    token = create_session(db, user)
    db.commit()
    set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: DbSession = Depends(get_db),
):
    if session_token:
        session = db.execute(
            select(Session).where(Session.token_hash == hash_session_token(session_token))
        ).scalar_one_or_none()
        if session is not None:
            db.delete(session)
            db.commit()
    clear_session_cookie(response)
    return None


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
