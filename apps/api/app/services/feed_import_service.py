from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FeedImportItem,
    FeedImportJob,
    FeedImportSourceType,
    User,
)

MAX_FEED_IMPORT_URLS = 200


@dataclass(frozen=True)
class FeedImportCandidate:
    source_title: str | None
    raw_url: str


@dataclass(frozen=True)
class PreparedFeedImportItem:
    source_title: str | None
    raw_url: str
    normalized_url: str
    dedupe_key: str


@dataclass(frozen=True)
class PreparedFeedImport:
    items: list[PreparedFeedImportItem]
    unique_count: int


def normalize_feed_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL 必须是 http 或 https 地址")
    return normalized


def parse_urls_text(text: str) -> list[FeedImportCandidate]:
    return [
        FeedImportCandidate(source_title=None, raw_url=line.strip())
        for line in text.splitlines()
        if line.strip()
    ]


def parse_opml_feeds(xml: str) -> list[FeedImportCandidate]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("OPML 解析失败") from exc

    candidates: list[FeedImportCandidate] = []
    for outline in root.iter("outline"):
        raw_url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlurl")
        if not raw_url:
            continue
        source_title = outline.attrib.get("title") or outline.attrib.get("text")
        candidates.append(
            FeedImportCandidate(
                source_title=source_title.strip() if source_title and source_title.strip() else None,
                raw_url=raw_url.strip(),
            )
        )
    return candidates


def prepare_import_candidates(candidates: list[FeedImportCandidate]) -> PreparedFeedImport:
    items: list[PreparedFeedImportItem] = []
    unique_keys: set[str] = set()

    for candidate in candidates:
        normalized_url = normalize_feed_url(candidate.raw_url)
        dedupe_key = normalized_url
        unique_keys.add(dedupe_key)
        items.append(
            PreparedFeedImportItem(
                source_title=candidate.source_title,
                raw_url=candidate.raw_url,
                normalized_url=normalized_url,
                dedupe_key=dedupe_key,
            )
        )

    if not items:
        raise ValueError("没有找到可导入的 Feed URL")

    if len(unique_keys) > MAX_FEED_IMPORT_URLS:
        raise ValueError(f"单次最多导入 {MAX_FEED_IMPORT_URLS} 个 Feed")

    return PreparedFeedImport(items=items, unique_count=len(unique_keys))


def create_feed_import_job(
    db: Session,
    user: User,
    source_type: FeedImportSourceType,
    prepared: PreparedFeedImport,
) -> FeedImportJob:
    job = FeedImportJob(
        user_id=user.id,
        source_type=source_type,
        total_count=len(prepared.items),
    )
    db.add(job)
    db.flush()

    for prepared_item in prepared.items:
        db.add(
            FeedImportItem(
                job_id=job.id,
                source_title=prepared_item.source_title,
                raw_url=prepared_item.raw_url,
                normalized_url=prepared_item.normalized_url,
                dedupe_key=prepared_item.dedupe_key,
            )
        )

    db.commit()
    return get_feed_import_job_for_user(db, user, job.id)


def get_feed_import_job_for_user(db: Session, user: User, job_id) -> FeedImportJob:
    job = db.execute(
        select(FeedImportJob)
        .options(selectinload(FeedImportJob.items))
        .where(FeedImportJob.id == job_id, FeedImportJob.user_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("import not found")
    return job
