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


def seed_article(client: TestClient, *, is_read: bool = False) -> UUID:
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
            is_read=is_read,
        )
        db.add(article)
        db.flush()
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
    article_id = seed_article(client, is_read=False)

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


def test_detail_read_state_and_reanalysis_use_existing_markdown(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    queued_ai_analysis: list[str] = []
    queued_extraction: list[str] = []
    monkeypatch.setattr(
        "app.tasks.analyze_article_task.delay",
        lambda article_id: queued_ai_analysis.append(article_id),
    )
    monkeypatch.setattr(
        "app.tasks.extract_article_task.delay",
        lambda article_id: queued_extraction.append(article_id),
    )
    article_id = seed_article(client, is_read=False)

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

    reanalyze_response = client.post(f"/articles/{article_id}/reanalyze")
    assert reanalyze_response.status_code == 202
    assert reanalyze_response.json() == {"status": "queued"}
    assert queued_ai_analysis == [str(article_id)]
    assert queued_extraction == []
