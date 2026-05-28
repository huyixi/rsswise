from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Feed
from app.schemas import FeedCreate
from app.services.feed_service import add_feed_from_url, delete_feed_by_id, list_feeds_for_api
from app.tasks import refresh_feed_task

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("")
def list_feeds(db: Session = Depends(get_db)):
    return list_feeds_for_api(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_feed(payload: FeedCreate, db: Session = Depends(get_db)):
    feed = add_feed_from_url(db, str(payload.url))
    return {"id": str(feed.id), "title": feed.title, "url": feed.url}


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_feed(feed_id: UUID, db: Session = Depends(get_db)):
    if db.get(Feed, feed_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feed not found")
    refresh_feed_task.delay(str(feed_id))
    return {"feed_id": str(feed_id), "status": "queued"}


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(feed_id: UUID, db: Session = Depends(get_db)):
    delete_feed_by_id(db, feed_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
