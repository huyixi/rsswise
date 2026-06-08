from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import (
    AnalysisStatus,
    Article,
    ExtractionStatus,
    User,
    UserArticleState,
    UserFeedSubscription,
)
from app.services.analysis_events import (
    format_sse_event,
    get_redis_client,
    read_analysis_events,
)
from app.tasks import AI_PRIORITY_USER_OPENED, analyze_article_task

router = APIRouter(prefix="/articles", tags=["articles"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def single_sse_response(event_type: str, payload: dict, event_id: str = "0-0"):
    return StreamingResponse(
        iter([format_sse_event(event_id, event_type, payload)]),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article not found",
        )
    return article


def set_read_state(db: Session, user: User, article_id: UUID, is_read: bool) -> None:
    state = db.get(UserArticleState, (user.id, article_id))
    if state is None:
        state = UserArticleState(user_id=user.id, article_id=article_id, is_read=is_read)
        db.add(state)
    else:
        state.is_read = is_read
    db.commit()


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
            "published_at": article.published_at.isoformat()
            if article.published_at
            else None,
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


@router.get("/{article_id}/analysis/events")
def stream_analysis_events(
    article_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = get_subscribed_article_or_404(article_id, current_user, db)
    analysis = article.ai_analysis

    if article.content is None or article.content.extraction_status != ExtractionStatus.success:
        return single_sse_response(
            "waiting_content",
            {"article_id": str(article_id)},
        )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article analysis not found",
        )

    if analysis.analysis_status == AnalysisStatus.success:
        return single_sse_response("done", {"article_id": str(article_id)})

    if analysis.analysis_status == AnalysisStatus.failed:
        return single_sse_response("error", {"message": "AI 分析失败"})

    if analysis.analysis_status == AnalysisStatus.pending:
        analyze_article_task.apply_async(
            args=[str(article_id)],
            priority=AI_PRIORITY_USER_OPENED,
        )

    redis_client = get_redis_client()
    last_event_id = request.headers.get("last-event-id")

    def body():
        for event_id, event_type, payload in read_analysis_events(
            redis_client,
            article_id,
            last_event_id=last_event_id,
        ):
            yield format_sse_event(event_id, event_type, payload)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    set_read_state(db, current_user, article_id, True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{article_id}/unread", status_code=status.HTTP_204_NO_CONTENT)
def mark_unread(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    set_read_state(db, current_user, article_id, False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
