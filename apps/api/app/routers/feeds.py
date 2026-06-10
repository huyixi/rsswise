from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import Feed, FeedImportSourceType, User
from app.schemas import FeedCreate, FeedImportCreate, FeedImportJobRead
from app.services.feed_import_service import (
    create_feed_import_job,
    get_feed_import_job_for_user,
    parse_opml_feeds,
    parse_urls_text,
    prepare_import_candidates,
)
from app.services.feed_service import (
    add_feed_from_url,
    delete_feed_subscription,
    list_feeds_for_api,
    user_is_subscribed_to_feed,
)
from app.tasks import import_feeds_task, refresh_feed_task

router = APIRouter(prefix="/feeds", tags=["feeds"])


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


@router.post("/imports", response_model=FeedImportJobRead, status_code=status.HTTP_201_CREATED)
def create_feed_import(
    payload: FeedImportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        candidates = (
            parse_urls_text(payload.urls_text or "")
            if payload.source_type == FeedImportSourceType.urls
            else parse_opml_feeds(payload.opml_xml or "")
        )
        prepared = prepare_import_candidates(candidates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = create_feed_import_job(db, current_user, payload.source_type, prepared)
    import_feeds_task.delay(str(job.id))
    job.items = []
    return job


@router.get("/imports/{import_id}", response_model=FeedImportJobRead)
def get_feed_import(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_feed_import_job_for_user(db, current_user, import_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import not found") from exc


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
