from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
