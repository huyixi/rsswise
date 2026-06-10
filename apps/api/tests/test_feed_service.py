from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Feed, User, UserFeedSubscription
from app.services.feed_service import add_or_subscribe_feed_from_url, parse_feed_items


def test_parse_feed_items_keeps_design_fields():
    parsed = parse_feed_items(
        """
        <rss version="2.0"><channel>
          <title>Example Feed</title>
          <link>https://example.com</link>
          <item>
            <guid>post-1</guid>
            <title>First Post</title>
            <link>https://example.com/post-1</link>
            <author>Ada</author>
            <pubDate>Wed, 01 Jan 2026 00:00:00 GMT</pubDate>
            <description>Summary</description>
          </item>
        </channel></rss>
        """
    )

    assert parsed.feed_title == "Example Feed"
    assert parsed.site_url == "https://example.com"
    assert parsed.items[0].title == "First Post"
    assert parsed.items[0].guid == "post-1"
    assert parsed.items[0].summary_from_feed == "Summary"


def make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_local()


def make_user(db, email="user@example.com"):
    user = User(id=uuid4(), email=email, password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_add_or_subscribe_skips_existing_user_subscription():
    db = make_db()
    user = make_user(db)
    feed = Feed(title="Existing", url="https://example.com/feed.xml")
    db.add(feed)
    db.flush()
    db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))
    db.commit()

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "skipped"
    assert result.feed.id == feed.id


def test_add_or_subscribe_subscribes_existing_global_feed():
    db = make_db()
    user = make_user(db)
    feed = Feed(title="Existing", url="https://example.com/feed.xml")
    db.add(feed)
    db.commit()

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "subscribed"
    assert db.get(UserFeedSubscription, (user.id, feed.id)) is not None


def test_add_or_subscribe_creates_new_feed(mocker):
    db = make_db()
    user = make_user(db)
    mocker.patch(
        "app.services.feed_service.fetch_feed_xml",
        return_value="<rss><channel><title>Created</title><link>https://example.com</link></channel></rss>",
    )
    enqueue = mocker.patch("app.services.feed_service.enqueue_extraction")

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "created"
    assert result.feed.title == "Created"
    assert db.execute(select(Feed)).scalar_one().url == "https://example.com/feed.xml"
    enqueue.assert_called_once()
