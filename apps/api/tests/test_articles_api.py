from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import (
    AnalysisStatus,
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    Base,
    ExtractionStatus,
    Feed,
    ReadingRecommendation,
    UserArticleState,
    UserFeedSubscription,
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
    app.state.testing_session_local = testing_session_local

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return response.json()


def seed_article(
    client: TestClient,
    *,
    user_id: str,
    is_read: bool = False,
    ai_blocks: list[dict] | None = None,
) -> UUID:
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
                ai_blocks=ai_blocks,
            )
        )
        db.commit()
        return article.id


def seed_pending_article(client: TestClient, *, user_id: str) -> UUID:
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        feed = Feed(
            title="Pending Feed",
            url="https://example.com/pending-feed.xml",
            site_url="https://example.com",
        )
        article = Article(
            feed=feed,
            title="Pending Post",
            url="https://example.com/pending-post",
            author="Ada",
            published_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            summary_from_feed="Feed summary",
            guid="pending-post-1",
        )
        db.add(article)
        db.flush()
        db.add(UserFeedSubscription(user_id=UUID(user_id), feed_id=feed.id))
        db.add(
            ArticleContent(
                article_id=article.id,
                content_markdown="# Pending Post\n\nBody text.",
                extraction_status=ExtractionStatus.success,
            )
        )
        db.add(
            ArticleAIAnalysis(
                article_id=article.id,
                analysis_status=AnalysisStatus.pending,
            )
        )
        db.commit()
        return article.id


def test_recommendation_labels_are_design_values():
    labels = {
        ReadingRecommendation.deep_read.value: "值得精读",
        ReadingRecommendation.skim.value: "适合略读",
        ReadingRecommendation.skip.value: "可以跳过",
    }

    assert labels == {
        "deep_read": "值得精读",
        "skim": "适合略读",
        "skip": "可以跳过",
    }


def test_list_articles_supports_design_read_filters(client: TestClient):
    user = register(client)
    article_id = seed_article(client, user_id=user["id"], is_read=False)

    unread_response = client.get("/articles?status_filter=unread")

    assert unread_response.status_code == 200
    unread_articles = unread_response.json()
    assert len(unread_articles) == 1
    assert unread_articles[0]["id"] == str(article_id)
    assert unread_articles[0]["title"] == "Readable Post"
    assert unread_articles[0]["source_title"] == "Example Feed"
    assert unread_articles[0]["one_sentence_summary"] == "A concise reason to read."
    assert unread_articles[0]["reading_recommendation"] == "deep_read"
    assert unread_articles[0]["is_read"] is False

    assert client.get("/articles?status_filter=read").json() == []
    assert client.get("/articles?status_filter=favorites").status_code == 400


def test_list_articles_derives_summary_from_ai_blocks(client: TestClient):
    user = register(client)
    ai_blocks = [
        {
            "type": "summary",
            "title": "一句话摘要",
            "content": "来自 block 的摘要。",
            "order": 10,
        },
        {
            "type": "reading_question",
            "title": "带读问题",
            "content": "这篇文章要回答什么？",
            "order": 20,
        },
        {
            "type": "reading_reason",
            "title": "阅读理由",
            "content": "来自 block 的理由。",
            "order": 30,
        },
    ]
    article_id = seed_article(client, user_id=user["id"], is_read=False, ai_blocks=ai_blocks)

    unread_response = client.get("/articles?status_filter=unread")
    unread_articles = unread_response.json()
    assert unread_articles[0]["one_sentence_summary"] == "来自 block 的摘要。"

    detail = client.get(f"/articles/{article_id}").json()
    assert detail["ai_blocks"][0]["type"] == "summary"
    assert detail["one_sentence_summary"] == "来自 block 的摘要。"
    assert detail["reading_reason"] == "来自 block 的理由。"


def test_detail_read_state_and_reanalysis_route_is_removed(client: TestClient):
    user = register(client)
    article_id = seed_article(client, user_id=user["id"], is_read=False)

    detail_response = client.get(f"/articles/{article_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["content_markdown"] == "# Readable Post\n\nBody text."
    assert detail["extraction_status"] == "success"
    assert detail["analysis_status"] == "success"
    assert detail["reading_reason"] == "The article has durable insight."

    read_response = client.post(f"/articles/{article_id}/read")
    assert read_response.status_code == 204
    assert client.get("/articles?status_filter=read").json()[0]["id"] == str(article_id)

    unread_response = client.post(f"/articles/{article_id}/unread")
    assert unread_response.status_code == 204
    assert client.get("/articles?status_filter=unread").json()[0]["id"] == str(article_id)

    assert client.post(f"/articles/{article_id}/reanalyze").status_code == 404


def test_articles_require_login(client: TestClient):
    assert client.get("/articles").status_code == 401


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
        assert article is not None
        db.add(UserFeedSubscription(user_id=UUID(second_user["id"]), feed_id=article.feed_id))
        db.commit()

    assert second_client.get("/articles?status_filter=read").json() == []
    assert second_client.get("/articles?status_filter=unread").json()[0]["id"] == str(article_id)


def test_analysis_events_pending_article_enqueues_priority_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    user = register(client)
    article_id = seed_pending_article(client, user_id=user["id"])
    queued: list[tuple[list[str], int]] = []
    redis_client = object()

    monkeypatch.setattr("app.routers.articles.get_redis_client", lambda: redis_client)
    monkeypatch.setattr(
        "app.routers.articles.analyze_article_task.apply_async",
        lambda args, priority: queued.append((args, priority)),
    )
    monkeypatch.setattr(
        "app.routers.articles.read_analysis_events",
        lambda client, article_id, last_event_id=None: iter(
            [
                ("1-0", "started", {"article_id": str(article_id)}),
                ("2-0", "done", {"article_id": str(article_id)}),
            ]
        ),
    )

    response = client.get(f"/articles/{article_id}/analysis/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: started" in response.text
    assert "event: done" in response.text
    assert queued == [([str(article_id)], 0)]


def test_analysis_events_success_article_returns_done_without_queue(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    user = register(client)
    article_id = seed_article(client, user_id=user["id"])

    monkeypatch.setattr(
        "app.routers.articles.analyze_article_task.apply_async",
        lambda args, priority: pytest.fail("success article should not be queued"),
    )

    response = client.get(f"/articles/{article_id}/analysis/events")

    assert response.status_code == 200
    assert "event: done" in response.text
    assert str(article_id) in response.text


def test_analysis_events_require_subscription(client: TestClient):
    first_user = register(client, "first@example.com")
    article_id = seed_article(client, user_id=first_user["id"])

    second_client = TestClient(app)
    register(second_client, "second@example.com")

    assert second_client.get(f"/articles/{article_id}/analysis/events").status_code == 404
