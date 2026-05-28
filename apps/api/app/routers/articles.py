from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Article
from app.tasks import analyze_article_task

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
def list_articles(status_filter: str = "all", db: Session = Depends(get_db)):
    if status_filter not in {"all", "read", "unread"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid status_filter",
        )

    statement = (
        select(Article)
        .options(joinedload(Article.feed), joinedload(Article.ai_analysis))
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
    )
    if status_filter == "read":
        statement = statement.where(Article.is_read.is_(True))
    if status_filter == "unread":
        statement = statement.where(Article.is_read.is_(False))

    articles = db.execute(statement).scalars().all()
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
            "is_read": article.is_read,
        }
        for article in articles
    ]


@router.get("/{article_id}")
def get_article(article_id: UUID, db: Session = Depends(get_db)):
    article = db.execute(
        select(Article)
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
def mark_read(article_id: UUID, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article not found",
        )
    article.is_read = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{article_id}/unread", status_code=status.HTTP_204_NO_CONTENT)
def mark_unread(article_id: UUID, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article not found",
        )
    article.is_read = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{article_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(article_id: UUID, db: Session = Depends(get_db)):
    if db.get(Article, article_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="article not found",
        )
    analyze_article_task.delay(str(article_id))
    return {"status": "queued"}
