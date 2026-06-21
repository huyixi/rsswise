from pathlib import Path

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleAIAnalysisLog,
    ArticleContent,
    ExternalLinkCollection,
    ExternalLinkCollectionItem,
    ExternalLinkCollectionStatus,
    ExternalLinkItemStatus,
    ExternalLinkSourceMode,
    Feed,
    Session,
    User,
    UserArticleState,
    UserFeedSubscription,
)


def fk_for(column):
    (foreign_key,) = column.foreign_keys
    return foreign_key


def test_models_match_design_entities():
    assert Feed.__tablename__ == "feeds"
    assert Article.__tablename__ == "articles"
    assert ArticleContent.__tablename__ == "article_contents"
    assert ArticleAIAnalysis.__tablename__ == "article_ai_analyses"
    assert ArticleAIAnalysisLog.__tablename__ == "article_ai_analysis_logs"


def test_multi_user_tables_are_declared():
    assert User.__tablename__ == "users"
    assert Session.__tablename__ == "sessions"
    assert UserFeedSubscription.__tablename__ == "user_feed_subscriptions"
    assert UserArticleState.__tablename__ == "user_article_states"


def test_external_link_collection_tables_are_declared():
    assert ExternalLinkCollection.__tablename__ == "external_link_collections"
    assert ExternalLinkCollectionItem.__tablename__ == "external_link_collection_items"
    assert [status.value for status in ExternalLinkCollectionStatus] == [
        "collecting",
        "prepared",
        "generated",
        "sent",
        "failed",
    ]
    assert [status.value for status in ExternalLinkItemStatus] == [
        "pending",
        "extracting",
        "success",
        "failed",
        "timed_out",
    ]
    assert [mode.value for mode in ExternalLinkSourceMode] == [
        "auto",
        "summary_from_feed",
        "content_markdown",
    ]


def test_external_link_collection_schema_metadata():
    source_article_fk = fk_for(ExternalLinkCollection.__table__.c.source_article_id)

    assert Article.__table__.c.feed_id.nullable is True
    assert source_article_fk.column.table.name == "articles"
    assert source_article_fk.column.name == "id"
    assert source_article_fk.ondelete == "CASCADE"

    for column_name in ("source_article_id", "target_send_date", "status"):
        assert ExternalLinkCollection.__table__.c[column_name].index is True


def test_external_link_collection_item_schema_metadata():
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in ExternalLinkCollectionItem.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    collection_fk = fk_for(ExternalLinkCollectionItem.__table__.c.collection_id)
    article_fk = fk_for(ExternalLinkCollectionItem.__table__.c.article_id)

    assert ("collection_id", "normalized_url") in constraints
    assert ("collection_id", "position") in constraints

    assert collection_fk.column.table.name == "external_link_collections"
    assert collection_fk.column.name == "id"
    assert collection_fk.ondelete == "CASCADE"
    assert article_fk.column.table.name == "articles"
    assert article_fk.column.name == "id"
    assert article_fk.ondelete == "SET NULL"

    for column_name in ("collection_id", "article_id", "normalized_url", "status"):
        assert ExternalLinkCollectionItem.__table__.c[column_name].index is True


def test_external_link_relationships_configure_without_ambiguity():
    configure_mappers()


def test_external_link_migration_cleans_feedless_articles_before_downgrade_not_null():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0006_external_link_collections.py"
    )
    migration_source = migration_path.read_text()
    downgrade_source = migration_source.split("def downgrade() -> None:", maxsplit=1)[1]

    delete_feedless_articles = 'op.execute(sa.text("DELETE FROM articles WHERE feed_id IS NULL"))'
    make_feed_id_not_null = 'op.alter_column(\n        "articles",\n        "feed_id",'

    assert delete_feedless_articles in downgrade_source
    assert downgrade_source.index(delete_feedless_articles) < downgrade_source.index(
        make_feed_id_not_null
    )
