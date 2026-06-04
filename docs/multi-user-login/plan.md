# Multi-User Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add open email/password registration, HTTP-only cookie sessions, per-user Feed subscriptions, and per-user article read state.

**Architecture:** Keep Feed, Article, content extraction, and AI analysis as shared content tables. Add users, sessions, user subscriptions, and user article states, then route all business API access through the authenticated user dependency. The frontend reads `/auth/me`, protects business routes, and sends cookies with every API request.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, SQLite test database, React, React Router, TanStack Query, Vite, TypeScript, coss UI components.

---

## File Structure

- Create `apps/api/app/core/security.py`: password hashing, password verification, session token generation, token hashing.
- Modify `apps/api/app/core/config.py`: session cookie name, session max age, secure cookie flag, initial migration user settings.
- Modify `apps/api/app/models.py`: add `User`, `Session`, `UserFeedSubscription`, and `UserArticleState` models and relationships.
- Create `apps/api/app/routers/auth.py`: register, login, logout, and current-user endpoints.
- Create `apps/api/app/dependencies/auth.py`: `get_current_user` session lookup dependency.
- Modify `apps/api/app/main.py`: include the auth router.
- Modify `apps/api/app/schemas.py`: auth request and response schemas.
- Modify `apps/api/app/services/feed_service.py`: shared Feed upsert plus per-user subscription operations.
- Modify `apps/api/app/routers/feeds.py`: require current user and operate on subscriptions.
- Modify `apps/api/app/routers/articles.py`: require current user, filter through subscriptions, use user read state.
- Create `apps/api/alembic/versions/0002_multi_user_auth.py`: add auth and user-state tables; migrate historical data.
- Create `apps/api/tests/test_auth_api.py`: auth API coverage.
- Create `apps/api/tests/test_feeds_api.py`: user-specific Feed API coverage.
- Modify `apps/api/tests/test_articles_api.py`: subscription filtering and per-user read-state coverage.
- Modify `apps/web/src/lib/api.ts`: include credentials and auth helpers.
- Modify `apps/web/src/lib/query-keys.ts`: add auth query keys.
- Create `apps/web/src/lib/auth.ts`: auth types and API functions.
- Create `apps/web/src/components/auth-gate.tsx`: route guard for authenticated pages.
- Create `apps/web/src/routes/login.tsx`: login screen.
- Create `apps/web/src/routes/register.tsx`: registration screen.
- Modify `apps/web/src/router.tsx`: add public auth routes and wrap business routes.
- Modify `apps/web/src/App.tsx`: show current user email and logout button.
- Modify `apps/web/tests/e2e/*.spec.ts`: mock `/api/auth/me` before business-route tests.

---

## Task 1: Add Backend Security Utilities

**Files:**

- Create: `apps/api/app/core/security.py`
- Modify: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_auth_api.py`

- [ ] **Step 1: Write security utility tests**

Create `apps/api/tests/test_auth_api.py` with these initial tests:

```python
from app.core.security import (
    hash_password,
    hash_session_token,
    verify_password,
)


def test_password_hash_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_session_token_hash_is_stable_without_storing_raw_token():
    token = "raw-session-token"

    assert hash_session_token(token) == hash_session_token(token)
    assert hash_session_token(token) != token
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_auth_api.py -v
```

Expected: import failure because `app.core.security` does not exist.

- [ ] **Step 3: Implement `apps/api/app/core/security.py`**

Add:

```python
import hashlib
import hmac
import secrets

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"{PASSWORD_ALGORITHM}$"
        f"{PASSWORD_ITERATIONS}$"
        f"{salt.hex()}$"
        f"{digest.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PASSWORD_ALGORITHM:
        return False

    expected = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations),
    ).hex()
    return hmac.compare_digest(expected, digest_hex)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Add config values**

Modify `apps/api/app/core/config.py`:

```python
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

- [ ] **Step 5: Verify security utility tests pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_auth_api.py -v
```

Expected: 2 tests pass.

---

## Task 2: Add Multi-User Database Models and Migration

**Files:**

- Modify: `apps/api/app/models.py`
- Create: `apps/api/alembic/versions/0002_multi_user_auth.py`
- Test: `apps/api/tests/test_models.py`

- [ ] **Step 1: Add model tests**

Append to `apps/api/tests/test_models.py`:

```python
from app.models import (
    Session,
    User,
    UserArticleState,
    UserFeedSubscription,
)


def test_multi_user_tables_are_declared():
    assert User.__tablename__ == "users"
    assert Session.__tablename__ == "sessions"
    assert UserFeedSubscription.__tablename__ == "user_feed_subscriptions"
    assert UserArticleState.__tablename__ == "user_article_states"
```

- [ ] **Step 2: Run the failing model test**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_models.py::test_multi_user_tables_are_declared -v
```

Expected: import failure for the new model names.

- [ ] **Step 3: Add models**

Modify `apps/api/app/models.py` to import `Integer` if needed only for indexes are not used, and add these models after `ArticleAIAnalysis`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    feed_subscriptions: Mapped[list["UserFeedSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    article_states: Mapped[list["UserArticleState"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class UserFeedSubscription(Base):
    __tablename__ = "user_feed_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="feed_subscriptions")
    feed: Mapped[Feed] = relationship()


class UserArticleState(Base):
    __tablename__ = "user_article_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped[User] = relationship(back_populates="article_states")
    article: Mapped[Article] = relationship()
```

- [ ] **Step 4: Create migration**

Create `apps/api/alembic/versions/0002_multi_user_auth.py` with:

```python
"""multi user auth

Revision ID: 0002_multi_user_auth
Revises: 0001_initial
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime
import os
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.security import hash_password

revision: str = "0002_multi_user_auth"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "user_feed_subscriptions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "feed_id"),
    )

    op.create_table(
        "user_article_states",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "article_id"),
    )
    op.create_index("ix_user_article_states_is_read", "user_article_states", ["is_read"])

    _migrate_existing_data()


def _migrate_existing_data() -> None:
    bind = op.get_bind()
    feed_count = bind.execute(sa.text("select count(*) from feeds")).scalar_one()
    if feed_count == 0:
        return

    email = os.environ.get("INITIAL_USER_EMAIL", "").strip().lower()
    password = os.environ.get("INITIAL_USER_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "INITIAL_USER_EMAIL and INITIAL_USER_PASSWORD are required "
            "when migrating existing RSSWise data"
        )

    user_id = uuid.uuid4()
    now = datetime.utcnow()
    bind.execute(
        sa.text(
            """
            insert into users (id, email, password_hash, created_at)
            values (:id, :email, :password_hash, :created_at)
            """
        ),
        {
            "id": user_id,
            "email": email,
            "password_hash": hash_password(password),
            "created_at": now,
        },
    )
    bind.execute(
        sa.text(
            """
            insert into user_feed_subscriptions (user_id, feed_id, created_at)
            select :user_id, id, :created_at
            from feeds
            """
        ),
        {"user_id": user_id, "created_at": now},
    )
    bind.execute(
        sa.text(
            """
            insert into user_article_states (user_id, article_id, is_read, updated_at)
            select :user_id, id, is_read, :updated_at
            from articles
            """
        ),
        {"user_id": user_id, "updated_at": now},
    )


def downgrade() -> None:
    op.drop_index("ix_user_article_states_is_read", table_name="user_article_states")
    op.drop_table("user_article_states")
    op.drop_table("user_feed_subscriptions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 5: Verify model test passes**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_models.py::test_multi_user_tables_are_declared -v
```

Expected: test passes.

- [ ] **Step 6: Verify migration syntax**

Run:

```bash
cd apps/api && uv run --no-sync python -m py_compile alembic/versions/0002_multi_user_auth.py
```

Expected: no output and exit code 0.

---

## Task 3: Add Auth API and Auth Dependency

**Files:**

- Create: `apps/api/app/dependencies/__init__.py`
- Create: `apps/api/app/dependencies/auth.py`
- Create: `apps/api/app/routers/auth.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/schemas.py`
- Test: `apps/api/tests/test_auth_api.py`

- [ ] **Step 1: Extend auth API tests**

Append to `apps/api/tests/test_auth_api.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base, Session, User


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[DbSession]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.testing_session_local = testing_session_local

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_register_sets_session_cookie_and_returns_user(client: TestClient):
    response = client.post(
        "/auth/register",
        json={"email": "USER@Example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert "rsswise_session" in response.cookies

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_register_rejects_duplicate_email(client: TestClient):
    payload = {"email": "user@example.com", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409


def test_login_and_logout(client: TestClient):
    payload = {"email": "user@example.com", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401

    login_response = client.post("/auth/login", json=payload)

    assert login_response.status_code == 200
    assert login_response.json()["email"] == "user@example.com"
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_login_rejects_wrong_password(client: TestClient):
    assert client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    ).status_code == 201
    assert client.post("/auth/logout").status_code == 204

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
```

- [ ] **Step 2: Run failing auth API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_auth_api.py -v
```

Expected: `/auth/register` returns 404 because the router is not implemented.

- [ ] **Step 3: Add auth schemas**

Modify `apps/api/app/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("invalid email")
        return email


class UserRead(BaseModel):
    id: UUID
    email: str

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Add auth dependency**

Create `apps/api/app/dependencies/auth.py`:

```python
from datetime import datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.config import settings
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models import Session, User


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: DbSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    session = db.execute(
        select(Session)
        .where(Session.token_hash == hash_session_token(session_token))
        .options(joinedload(Session.user))
    ).scalar_one_or_none()
    if session is None or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    return session.user
```

Create `apps/api/app/dependencies/__init__.py` as an empty file.

- [ ] **Step 5: Add auth router**

Create `apps/api/app/routers/auth.py`:

```python
from datetime import datetime, timedelta

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
            expires_at=datetime.utcnow() + timedelta(seconds=settings.session_max_age_seconds),
        )
    )
    return token


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRequest, response: Response, db: DbSession = Depends(get_db)):
    email = normalize_email(str(payload.email))
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

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
```

- [ ] **Step 6: Include auth router**

Modify `apps/api/app/main.py`:

```python
from app.routers import articles, auth, feeds

app.include_router(auth.router)
app.include_router(feeds.router)
app.include_router(articles.router)
```

- [ ] **Step 7: Verify auth API tests pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_auth_api.py -v
```

Expected: auth utility and auth API tests pass.

---

## Task 4: Require Auth and User Subscriptions for Feed APIs

**Files:**

- Modify: `apps/api/app/services/feed_service.py`
- Modify: `apps/api/app/routers/feeds.py`
- Test: `apps/api/tests/test_feeds_api.py`

- [ ] **Step 1: Add Feed API tests**

Create `apps/api/tests/test_feeds_api.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import UUID

from app.db.session import get_db
from app.main import app
from app.models import Base, Feed, UserFeedSubscription


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
    app.state.testing_session_local = testing_session_local

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, email: str):
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return response.json()


def test_feed_list_requires_login(client: TestClient):
    assert client.get("/feeds").status_code == 401


def test_feed_list_only_returns_current_user_subscriptions(client: TestClient):
    first_user = register(client, "first@example.com")
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        feed = Feed(title="Shared Feed", url="https://example.com/feed.xml")
        other_feed = Feed(title="Other Feed", url="https://other.example.com/feed.xml")
        db.add_all([feed, other_feed])
        db.flush()
        db.add(UserFeedSubscription(user_id=UUID(first_user["id"]), feed_id=feed.id))
        db.commit()

    response = client.get("/feeds")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Shared Feed"]


def test_deleting_feed_only_removes_current_user_subscription(client: TestClient):
    first_user = register(client, "first@example.com")
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        feed = Feed(title="Shared Feed", url="https://example.com/feed.xml")
        db.add(feed)
        db.flush()
        db.add(UserFeedSubscription(user_id=UUID(first_user["id"]), feed_id=feed.id))
        db.commit()
        feed_id = feed.id

    response = client.delete(f"/feeds/{feed_id}")

    assert response.status_code == 204
    with session_local() as db:
        assert db.get(Feed, feed_id) is not None
        assert db.execute(select(UserFeedSubscription)).scalars().all() == []
```

- [ ] **Step 2: Run failing Feed API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: tests fail because Feed routes do not require auth and do not filter subscriptions.

- [ ] **Step 3: Update Feed service functions**

Modify `apps/api/app/services/feed_service.py`:

```python
from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed, User, UserFeedSubscription


def list_feeds_for_api(db: Session, user: User) -> list[dict]:
    feeds = db.execute(
        select(Feed)
        .join(UserFeedSubscription, UserFeedSubscription.feed_id == Feed.id)
        .where(UserFeedSubscription.user_id == user.id)
        .order_by(UserFeedSubscription.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": str(feed.id),
            "title": feed.title,
            "url": feed.url,
            "site_url": feed.site_url,
            "favicon_url": feed.favicon_url,
            "last_fetched_at": feed.last_fetched_at.isoformat() if feed.last_fetched_at else None,
        }
        for feed in feeds
    ]


def add_feed_from_url(db: Session, url: str, user: User) -> Feed:
    feed = db.execute(select(Feed).where(Feed.url == url)).scalar_one_or_none()
    new_articles: list[Article] = []

    if feed is None:
        parsed = parse_feed_items(fetch_feed_xml(url))
        feed = Feed(url=url, title=parsed.feed_title)
        db.add(feed)
        feed.title = parsed.feed_title
        feed.site_url = parsed.site_url
        feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
        feed.last_fetched_at = datetime.utcnow()
        db.flush()
        new_articles = upsert_feed_articles(db, feed, parsed)

    subscription = db.get(UserFeedSubscription, (user.id, feed.id))
    if subscription is None:
        db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))

    db.commit()
    enqueue_extraction(new_articles)
    return feed


def user_is_subscribed_to_feed(db: Session, user: User, feed_id: UUID) -> bool:
    return db.get(UserFeedSubscription, (user.id, feed_id)) is not None


def delete_feed_subscription(db: Session, feed_id: UUID, user: User) -> None:
    subscription = db.get(UserFeedSubscription, (user.id, feed_id))
    if subscription is not None:
        db.delete(subscription)
        db.commit()
```

Keep `refresh_feed_by_id` unchanged because background refresh operates on shared Feed rows.

- [ ] **Step 4: Update Feed router**

Modify `apps/api/app/routers/feeds.py`:

```python
from app.dependencies.auth import get_current_user
from app.models import Feed, User
from app.services.feed_service import (
    add_feed_from_url,
    delete_feed_subscription,
    list_feeds_for_api,
    user_is_subscribed_to_feed,
)


@router.get("")
def list_feeds(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_feeds_for_api(db, current_user)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_feed(
    payload: FeedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feed = add_feed_from_url(db, str(payload.url), current_user)
    return {"id": str(feed.id), "title": feed.title, "url": feed.url}


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_feed(
    feed_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if db.get(Feed, feed_id) is None or not user_is_subscribed_to_feed(db, current_user, feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feed not found")
    refresh_feed_task.delay(str(feed_id))
    return {"feed_id": str(feed_id), "status": "queued"}


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(
    feed_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_feed_subscription(db, feed_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Verify Feed API tests pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: Feed API tests pass.

---

## Task 5: Scope Articles by Subscription and User Read State

**Files:**

- Modify: `apps/api/app/routers/articles.py`
- Test: `apps/api/tests/test_articles_api.py`

- [ ] **Step 1: Update article API tests for auth**

Modify the existing fixture and helper usage in `apps/api/tests/test_articles_api.py` so tests register a user before business API calls:

```python
def register(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return response.json()
```

Update `seed_article` so the `is_read` argument creates the current user's read state:

```python
from app.models import UserArticleState, UserFeedSubscription


def seed_article(client: TestClient, *, user_id: str, is_read: bool = False) -> UUID:
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        feed = Feed(
            title="Example Feed",
            url="https://example.com/feed.xml",
            site_url="https://example.com",
        )
        article = Article(
            feed=feed,
            title="Readable Post",
            url="https://example.com/readable-post",
            author="Ada",
            published_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            summary_from_feed="Feed summary",
            guid="post-1",
            is_read=False,
        )
        db.add(article)
        db.flush()
        db.add(UserFeedSubscription(user_id=UUID(user_id), feed_id=feed.id))
        db.add(UserArticleState(user_id=UUID(user_id), article_id=article.id, is_read=is_read))
        db.add(
            ArticleContent(
                article_id=article.id,
                content_markdown="# Readable Post\n\nBody text.",
                extraction_status=ExtractionStatus.success,
            )
        )
        db.add(
            ArticleAIAnalysis(
                article_id=article.id,
                one_sentence_summary="A concise reason to read.",
                reading_recommendation=ReadingRecommendation.deep_read,
                reading_reason="The article has durable insight.",
                analysis_status=AnalysisStatus.success,
            )
        )
        db.commit()
        return article.id
```

Add a new test:

```python
def test_articles_require_login(client: TestClient):
    assert client.get("/articles").status_code == 401
```

Add a per-user isolation test:

```python
def test_read_state_is_isolated_per_user(client: TestClient):
    first_user = register(client, "first@example.com")
    article_id = seed_article(client, user_id=first_user["id"], is_read=False)
    assert client.post(f"/articles/{article_id}/read").status_code == 204
    assert client.get("/articles?status_filter=read").json()[0]["id"] == str(article_id)

    second_client = TestClient(app)
    second_user = register(second_client, "second@example.com")
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        article = db.get(Article, article_id)
        db.add(UserFeedSubscription(user_id=UUID(second_user["id"]), feed_id=article.feed_id))
        db.commit()

    assert second_client.get("/articles?status_filter=read").json() == []
    assert second_client.get("/articles?status_filter=unread").json()[0]["id"] == str(article_id)
```

- [ ] **Step 2: Run failing article API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py -v
```

Expected: failures because article routes still use global `Article.is_read`.

- [ ] **Step 3: Add article authorization helpers**

Modify `apps/api/app/routers/articles.py` imports:

```python
from sqlalchemy import and_, or_, select

from app.dependencies.auth import get_current_user
from app.models import Article, User, UserArticleState, UserFeedSubscription
```

Add helper functions:

```python
def subscribed_article_statement(user: User):
    return (
        select(Article)
        .join(UserFeedSubscription, UserFeedSubscription.feed_id == Article.feed_id)
        .where(UserFeedSubscription.user_id == user.id)
    )


def get_subscribed_article_or_404(article_id: UUID, user: User, db: Session) -> Article:
    article = db.execute(
        subscribed_article_statement(user)
        .where(Article.id == article_id)
        .options(
            joinedload(Article.feed),
            joinedload(Article.content),
            joinedload(Article.ai_analysis),
        )
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    return article


def set_read_state(db: Session, user: User, article_id: UUID, is_read: bool) -> None:
    state = db.get(UserArticleState, (user.id, article_id))
    if state is None:
        state = UserArticleState(user_id=user.id, article_id=article_id, is_read=is_read)
        db.add(state)
    else:
        state.is_read = is_read
    db.commit()
```

- [ ] **Step 4: Update list articles**

Replace `list_articles` with:

```python
@router.get("")
def list_articles(
    status_filter: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status_filter not in {"all", "read", "unread"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid status_filter",
        )

    statement = (
        subscribed_article_statement(current_user)
        .outerjoin(
            UserArticleState,
            and_(
                UserArticleState.article_id == Article.id,
                UserArticleState.user_id == current_user.id,
            ),
        )
        .options(joinedload(Article.feed), joinedload(Article.ai_analysis))
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
    )
    if status_filter == "read":
        statement = statement.where(UserArticleState.is_read.is_(True))
    if status_filter == "unread":
        statement = statement.where(
            or_(UserArticleState.is_read.is_(False), UserArticleState.article_id.is_(None))
        )

    rows = db.execute(statement.add_columns(UserArticleState.is_read)).all()
    return [
        {
            "id": str(article.id),
            "title": article.title,
            "source_title": article.feed.title,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "one_sentence_summary": article.ai_analysis.one_sentence_summary
            if article.ai_analysis
            else None,
            "reading_recommendation": article.ai_analysis.reading_recommendation.value
            if article.ai_analysis and article.ai_analysis.reading_recommendation
            else None,
            "is_read": bool(is_read),
        }
        for article, is_read in rows
    ]
```

- [ ] **Step 5: Update detail and mutations**

Update `get_article`, `mark_read`, `mark_unread`, and `reanalyze` to require `current_user` and use `get_subscribed_article_or_404`.

For `get_article`, keep the current response shape and change only authorization:

```python
@router.get("/{article_id}")
def get_article(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = get_subscribed_article_or_404(article_id, current_user, db)

    return {
        "id": str(article.id),
        "title": article.title,
        "source_title": article.feed.title,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "url": article.url,
        "one_sentence_summary": article.ai_analysis.one_sentence_summary
        if article.ai_analysis
        else None,
        "reading_recommendation": article.ai_analysis.reading_recommendation.value
        if article.ai_analysis and article.ai_analysis.reading_recommendation
        else None,
        "reading_reason": article.ai_analysis.reading_reason if article.ai_analysis else None,
        "content_markdown": article.content.content_markdown if article.content else None,
        "extraction_status": article.content.extraction_status.value if article.content else None,
        "analysis_status": article.ai_analysis.analysis_status.value if article.ai_analysis else None,
    }
```

For `mark_read`:

```python
@router.post("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    set_read_state(db, current_user, article_id, True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

For `mark_unread`:

```python
@router.post("/{article_id}/unread", status_code=status.HTTP_204_NO_CONTENT)
def mark_unread(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    set_read_state(db, current_user, article_id, False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

For `reanalyze`:

```python
@router.post("/{article_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    analyze_article_task.delay(str(article_id))
    return {"status": "queued"}
```

- [ ] **Step 6: Verify article API tests pass**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py -v
```

Expected: article API tests pass.

---

## Task 6: Add Frontend Auth API, Routes, and Route Guard

**Files:**

- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/query-keys.ts`
- Create: `apps/web/src/lib/auth.ts`
- Create: `apps/web/src/components/auth-gate.tsx`
- Create: `apps/web/src/routes/login.tsx`
- Create: `apps/web/src/routes/register.tsx`
- Modify: `apps/web/src/router.tsx`

- [ ] **Step 1: Update API fetch credentials**

Modify all fetch calls in `apps/web/src/lib/api.ts` to include credentials:

```ts
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
  })
  return parseResponse<T>(response)
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  return parseResponse<T>(response)
}

export async function apiDelete<T = unknown>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
  })

  return parseResponse<T>(response)
}
```

- [ ] **Step 2: Add auth API helpers**

Create `apps/web/src/lib/auth.ts`:

```ts
import { apiGet, apiPost } from "@/lib/api"

export type CurrentUser = {
  id: string
  email: string
}

export type AuthPayload = {
  email: string
  password: string
}

export function getCurrentUser() {
  return apiGet<CurrentUser>("/auth/me")
}

export function login(payload: AuthPayload) {
  return apiPost<CurrentUser>("/auth/login", payload)
}

export function register(payload: AuthPayload) {
  return apiPost<CurrentUser>("/auth/register", payload)
}

export function logout() {
  return apiPost<void>("/auth/logout")
}
```

- [ ] **Step 3: Add auth query keys**

Modify `apps/web/src/lib/query-keys.ts`:

```ts
export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  articles: {
    all: ["articles"] as const,
    list: (status: string) => ["articles", "list", { status }] as const,
    detail: (id: string) => ["articles", "detail", id] as const,
  },
  feeds: {
    all: ["feeds"] as const,
    list: () => ["feeds", "list"] as const,
  },
}
```

- [ ] **Step 4: Add route guard**

Create `apps/web/src/components/auth-gate.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { Navigate, Outlet, useLocation } from "react-router-dom"

import { getCurrentUser } from "@/lib/auth"
import { queryKeys } from "@/lib/query-keys"

export function AuthGate() {
  const location = useLocation()
  const meQuery = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: getCurrentUser,
    retry: false,
  })

  if (meQuery.isLoading) {
    return (
      <main className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        加载中
      </main>
    )
  }

  if (meQuery.isError) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
```

- [ ] **Step 5: Add login page**

Create `apps/web/src/routes/login.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useLocation, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { login } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = "登录 - RSSWise"
  }, [])

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.auth.me, user)
      navigate(typeof location.state?.from === "string" ? location.state.from : "/articles", {
        replace: true,
      })
    },
    onError: (err) => setError(err.message),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const formData = new FormData(event.currentTarget)
    loginMutation.mutate({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 px-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-foreground">登录 RSSWise</h1>
        <p className="text-sm text-muted-foreground">使用邮箱和密码继续阅读。</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        <Input name="email" type="email" placeholder="邮箱" required />
        <Input name="password" type="password" placeholder="密码" required minLength={8} />
        {error ? <p className="text-sm text-destructive-foreground">{error}</p> : null}
        <Button type="submit" loading={loginMutation.isPending}>
          登录
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        还没有账号？{" "}
        <Link className="font-medium text-foreground" to="/register">
          注册
        </Link>
      </p>
    </main>
  )
}
```

- [ ] **Step 6: Add register page**

Create `apps/web/src/routes/register.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { register } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

export function RegisterPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = "注册 - RSSWise"
  }, [])

  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.auth.me, user)
      navigate("/articles", { replace: true })
    },
    onError: (err) => setError(err.message),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const formData = new FormData(event.currentTarget)
    registerMutation.mutate({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 px-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-foreground">注册 RSSWise</h1>
        <p className="text-sm text-muted-foreground">创建账号后直接开始订阅 Feed。</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        <Input name="email" type="email" placeholder="邮箱" required />
        <Input name="password" type="password" placeholder="密码" required minLength={8} />
        {error ? <p className="text-sm text-destructive-foreground">{error}</p> : null}
        <Button type="submit" loading={registerMutation.isPending}>
          注册
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        已有账号？{" "}
        <Link className="font-medium text-foreground" to="/login">
          登录
        </Link>
      </p>
    </main>
  )
}
```

- [ ] **Step 7: Update router**

Modify `apps/web/src/router.tsx`:

```tsx
import { createBrowserRouter, Navigate } from "react-router-dom"
import { App } from "./App"
import { AuthGate } from "./components/auth-gate"
import { FeedsPage } from "./routes/feeds/list"
import { HomePage } from "./routes/home"
import { LoginPage } from "./routes/login"
import { RegisterPage } from "./routes/register"
import { ArticleWorkbenchPage } from "./routes/articles/workbench"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <AuthGate />,
    children: [
      {
        path: "/",
        element: <App />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "articles", element: <ArticleWorkbenchPage /> },
          { path: "articles/:id", element: <Navigate to="/articles" replace /> },
          { path: "feeds", element: <FeedsPage /> },
        ],
      },
    ],
  },
])
```

- [ ] **Step 8: Verify frontend typecheck/build**

Run:

```bash
cd apps/web && pnpm build
```

Expected: build succeeds.

---

## Task 7: Add Header User Display and Logout

**Files:**

- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Add current user and logout mutation**

Modify imports in `apps/web/src/App.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query"
import { LogOutIcon } from "lucide-react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { getCurrentUser, logout } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
```

Inside `App`:

```tsx
const navigate = useNavigate()
const meQuery = useQuery({
  queryKey: queryKeys.auth.me,
  queryFn: getCurrentUser,
  retry: false,
})
const logoutMutation = useMutation({
  mutationFn: logout,
  onSettled: () => {
    queryClient.clear()
    navigate("/login", { replace: true })
  },
})
```

- [ ] **Step 2: Render user email and logout button**

In the header nav, add a right-aligned section:

```tsx
<div className="ml-auto flex min-w-0 items-center gap-2">
  <span className="hidden truncate text-sm text-muted-foreground sm:block">
    {meQuery.data?.email}
  </span>
  <Button
    type="button"
    variant="ghost"
    size="icon"
    aria-label="退出登录"
    loading={logoutMutation.isPending}
    onClick={() => logoutMutation.mutate()}
  >
    <LogOutIcon aria-hidden="true" className="size-4" />
  </Button>
</div>
```

- [ ] **Step 3: Verify frontend build**

Run:

```bash
cd apps/web && pnpm build
```

Expected: build succeeds.

---

## Task 8: Update End-to-End Test Setup

**Files:**

- Modify: `apps/web/tests/e2e/articles.spec.ts`
- Modify: `apps/web/tests/e2e/feeds.spec.ts`

- [ ] **Step 1: Add an authenticated-user mock helper**

In each E2E spec that opens a business route, update imports and add:

```ts
import type { Page } from "@playwright/test";

async function mockAuthenticatedUser(page: Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      json: { id: "00000000-0000-0000-0000-000000000001", email: "user@example.com" },
    });
  });
}
```

- [ ] **Step 2: Call the helper before business routes**

Before navigating to `/articles` or `/feeds`, call:

```ts
await mockAuthenticatedUser(page);
```

- [ ] **Step 3: Add unauthenticated redirect coverage**

Add this test to `apps/web/tests/e2e/feeds.spec.ts`:

```ts
test("redirects unauthenticated users to login", async ({ page }) => {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      json: { detail: "not authenticated" },
    });
  });

  await page.goto("/feeds");

  await expect(page).toHaveURL(/\/login$/);
});
```

- [ ] **Step 4: Run mocked frontend E2E tests**

Run:

```bash
cd apps/web && pnpm test:e2e
```

Expected: existing route-level Playwright tests pass with mocked API responses.

---

## Task 9: Final Verification

**Files:**

- Modify only files changed by previous tasks.

- [ ] **Step 1: Run backend auth tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_auth_api.py -v
```

Expected: all auth tests pass.

- [ ] **Step 2: Run backend Feed tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: all Feed API tests pass.

- [ ] **Step 3: Run backend article tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_articles_api.py -v
```

Expected: all article API tests pass.

- [ ] **Step 4: Run the full backend test suite**

Run:

```bash
cd apps/api && uv run --no-sync pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 5: Run backend lint**

Run:

```bash
cd apps/api && uv run --no-sync ruff check app tests
```

Expected: no lint errors.

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd apps/web && pnpm build
```

Expected: build succeeds.

- [ ] **Step 7: Run aggregate check**

Run:

```bash
make check
```

Expected: backend tests, backend lint, and frontend build pass.

---

## Self-Review

- Spec coverage: The tasks cover registration, login, logout, session cookies, route protection, user Feed subscriptions, user read state, shared content, historical data migration, and verification.
- Placeholder scan: The plan contains no unresolved placeholders or open-ended implementation notes.
- Type consistency: Backend model names, schema names, auth helper names, and frontend auth helper names are used consistently across tasks.
