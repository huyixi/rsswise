from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base, Feed, FeedImportJob, FeedImportSourceType, UserFeedSubscription


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


def test_create_url_import_requires_login(client: TestClient):
    response = client.post(
        "/feeds/imports",
        json={"source_type": "urls", "urls_text": "https://example.com/feed.xml"},
    )

    assert response.status_code == 401


def test_create_url_import_queues_job(client: TestClient, mocker):
    register(client, "importer@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")

    response = client.post(
        "/feeds/imports",
        json={
            "source_type": "urls",
            "urls_text": "https://example.com/feed.xml\nhttps://example.com/feed.xml",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "urls"
    assert data["status"] == "pending"
    assert data["total_count"] == 2
    assert data["items"] == []
    delay.assert_called_once_with(data["id"])


def test_create_opml_import_queues_job(client: TestClient, mocker):
    register(client, "opml@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")

    response = client.post(
        "/feeds/imports",
        json={
            "source_type": "opml",
            "opml_xml": "<opml><body><outline text='Example' xmlUrl='https://example.com/feed.xml' /></body></opml>",
        },
    )

    assert response.status_code == 201
    assert response.json()["total_count"] == 1
    delay.assert_called_once()


def test_create_import_rejects_too_many_unique_urls(client: TestClient, mocker):
    register(client, "limit@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")
    urls = "\n".join(f"https://example.com/{index}.xml" for index in range(201))

    response = client.post(
        "/feeds/imports",
        json={"source_type": "urls", "urls_text": urls},
    )

    assert response.status_code == 400
    assert "最多导入 200 个 Feed" in response.json()["detail"]
    delay.assert_not_called()


def test_get_import_only_returns_current_users_job(client: TestClient):
    first_user = register(client, "first-import@example.com")
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        job = FeedImportJob(
            user_id=UUID(first_user["id"]),
            source_type=FeedImportSourceType.urls,
            total_count=0,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    register(client, "second-import@example.com")

    response = client.get(f"/feeds/imports/{job_id}")

    assert response.status_code == 404
