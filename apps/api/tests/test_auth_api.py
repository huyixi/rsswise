from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, hash_session_token, verify_password
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models import Base, Session, User
from app.routers.auth import create_session


def test_password_hash_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_session_token_hash_is_stable_without_storing_raw_token():
    token = "raw-session-token"

    assert hash_session_token(token) == hash_session_token(token)
    assert hash_session_token(token) != token


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


def test_create_session_uses_utc_aware_expiration(client: TestClient):
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        user = User(email="user@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.flush()

        create_session(db, user)
        created_session = next(obj for obj in db.new if isinstance(obj, Session))

    assert created_session.expires_at.tzinfo is UTC


def test_current_user_compares_utc_aware_session_expiration():
    token = "raw-session-token"
    user = User(email="user@example.com", password_hash=hash_password("password123"))
    auth_session = Session(
        user=user,
        token_hash=hash_session_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    class Result:
        def scalar_one_or_none(self):
            return auth_session

    class Db:
        def execute(self, statement):
            return Result()

    current_user = get_current_user(session_token=token, db=Db())

    assert current_user.email == "user@example.com"
