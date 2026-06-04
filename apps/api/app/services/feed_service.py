from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.request import Request, urlopen
from uuid import UUID

import feedparser
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed, User, UserFeedSubscription


@dataclass(frozen=True)
class ParsedFeedItem:
    title: str
    url: str
    author: str | None
    published_at: datetime | None
    summary_from_feed: str | None
    cover_image_url: str | None
    guid: str | None


@dataclass(frozen=True)
class ParsedFeed:
    feed_title: str
    site_url: str | None
    items: list[ParsedFeedItem]


def parse_feed_items(xml: str) -> ParsedFeed:
    feed = feedparser.parse(xml)
    items: list[ParsedFeedItem] = []

    for entry in feed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            continue

        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime(*entry.published_parsed[:6])

        media = getattr(entry, "media_content", []) or getattr(entry, "media_thumbnail", [])
        cover_image_url = media[0].get("url") if media else None

        items.append(
            ParsedFeedItem(
                title=title,
                url=url,
                author=getattr(entry, "author", None),
                published_at=published_at,
                summary_from_feed=getattr(entry, "summary", None),
                cover_image_url=cover_image_url,
                guid=getattr(entry, "id", None),
            )
        )

    return ParsedFeed(
        feed_title=getattr(feed.feed, "title", None) or "Untitled Feed",
        site_url=getattr(feed.feed, "link", None),
        items=items,
    )


def fetch_feed_xml(url: str) -> str:
    request = Request(url, headers={"User-Agent": "RSSWise/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def list_feeds_for_api(db: Session, user: User) -> list[dict]:
    feeds = (
        db.execute(
            select(Feed)
            .join(UserFeedSubscription, UserFeedSubscription.feed_id == Feed.id)
            .where(UserFeedSubscription.user_id == user.id)
            .order_by(UserFeedSubscription.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(feed.id),
            "title": feed.title,
            "url": feed.url,
            "site_url": feed.site_url,
            "favicon_url": feed.favicon_url,
            "last_fetched_at": feed.last_fetched_at.isoformat() if feed.last_fetched_at else None,
        }
        for feed in feeds
    ]


def add_feed_from_url(db: Session, url: str, user: User) -> Feed:
    feed = db.execute(select(Feed).where(Feed.url == url)).scalar_one_or_none()
    new_articles: list[Article] = []

    if feed is None:
        parsed = parse_feed_items(fetch_feed_xml(url))
        feed = Feed(url=url, title=parsed.feed_title)
        db.add(feed)
        feed.title = parsed.feed_title
        feed.site_url = parsed.site_url
        feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
        feed.last_fetched_at = datetime.now(UTC).replace(tzinfo=None)
        db.flush()
        new_articles = upsert_feed_articles(db, feed, parsed)

    subscription = db.get(UserFeedSubscription, (user.id, feed.id))
    if subscription is None:
        db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))

    db.commit()
    enqueue_extraction(new_articles)
    return feed


def refresh_feed_by_id(db: Session, feed_id: UUID) -> int:
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise ValueError("feed not found")

    parsed = parse_feed_items(fetch_feed_xml(feed.url))
    feed.title = parsed.feed_title
    feed.site_url = parsed.site_url
    feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
    feed.last_fetched_at = datetime.now(UTC).replace(tzinfo=None)
    new_articles = upsert_feed_articles(db, feed, parsed)
    db.commit()
    enqueue_extraction(new_articles)
    return len(new_articles)


def delete_feed_by_id(db: Session, feed_id: UUID) -> None:
    feed = db.get(Feed, feed_id)
    if feed is not None:
        db.delete(feed)
        db.commit()


def user_is_subscribed_to_feed(db: Session, user: User, feed_id: UUID) -> bool:
    return db.get(UserFeedSubscription, (user.id, feed_id)) is not None


def delete_feed_subscription(db: Session, feed_id: UUID, user: User) -> None:
    subscription = db.get(UserFeedSubscription, (user.id, feed_id))
    if subscription is not None:
        db.delete(subscription)
        db.commit()


def upsert_feed_articles(db: Session, feed: Feed, parsed: ParsedFeed) -> list[Article]:
    new_articles: list[Article] = []
    for item in parsed.items:
        dedupe_conditions = [Article.url == item.url]
        if item.guid:
            dedupe_conditions.append(Article.guid == item.guid)

        existing = db.execute(select(Article).where(or_(*dedupe_conditions))).scalar_one_or_none()

        if existing is not None:
            existing.title = item.title
            existing.author = item.author
            existing.published_at = item.published_at
            existing.summary_from_feed = item.summary_from_feed
            existing.cover_image_url = item.cover_image_url
            existing.guid = item.guid
            continue

        article = Article(
            feed_id=feed.id,
            title=item.title,
            url=item.url,
            author=item.author,
            published_at=item.published_at,
            summary_from_feed=item.summary_from_feed,
            cover_image_url=item.cover_image_url,
            guid=item.guid,
        )
        db.add(article)
        db.flush()
        db.add(ArticleContent(article_id=article.id))
        db.add(ArticleAIAnalysis(article_id=article.id))
        new_articles.append(article)

    return new_articles


def enqueue_extraction(articles: list[Article]) -> None:
    from app.tasks import extract_article_task

    for article in articles:
        extract_article_task.delay(str(article.id))
