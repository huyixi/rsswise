from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import Article, User, UserArticleState, UserFeedSubscription
from app.tasks import analyze_article_task

router = APIRouter(prefix="/articles", tags=["articles"])


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


@router.post("/{article_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_subscribed_article_or_404(article_id, current_user, db)
    analyze_article_task.delay(str(article_id))
    return {"status": "queued"}
