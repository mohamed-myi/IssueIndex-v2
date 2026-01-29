"""Bookmark service. All queries filter by user_id to enforce authorization."""
import logging
from datetime import UTC, datetime
from uuid import UUID

from gim_database.models.persistence import BookmarkedIssue, PersonalNote
from pydantic import BaseModel
from sqlalchemy import delete, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.errors import BookmarkAlreadyExistsError

logger = logging.getLogger(__name__)


DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 50


class NoteSchema(BaseModel):
    id: UUID
    bookmark_id: UUID
    content: str
    updated_at: datetime


class BookmarkSchema(BaseModel):
    id: UUID
    issue_node_id: str
    github_url: str
    title_snapshot: str
    body_snapshot: str
    is_resolved: bool
    created_at: datetime
    notes_count: int = 0



async def create_bookmark(
    db: AsyncSession,
    user_id: UUID,
    issue_node_id: str,

    github_url: str,
    title_snapshot: str,
    body_snapshot: str,
) -> BookmarkSchema:
    existing_stmt = select(BookmarkedIssue).where(
        BookmarkedIssue.user_id == user_id,
        BookmarkedIssue.issue_node_id == issue_node_id,
    )
    result = await db.exec(existing_stmt)
    if result.first() is not None:
        raise BookmarkAlreadyExistsError()

    bookmark = BookmarkedIssue(
        user_id=user_id,
        issue_node_id=issue_node_id,
        github_url=github_url,
        title_snapshot=title_snapshot,
        body_snapshot=body_snapshot,
        is_resolved=False,
    )

    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)

    logger.info(f"Created bookmark {bookmark.id} for user {user_id}")
    logger.info(f"Created bookmark {bookmark.id} for user {user_id}")
    return BookmarkSchema(
        id=bookmark.id,
        issue_node_id=bookmark.issue_node_id,
        github_url=bookmark.github_url,
        title_snapshot=bookmark.title_snapshot,
        body_snapshot=bookmark.body_snapshot,
        is_resolved=bookmark.is_resolved,
        created_at=bookmark.created_at,
        notes_count=0,
    )


async def list_bookmarks(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,

) -> tuple[list[BookmarkSchema], int, bool]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE

    offset = (page - 1) * page_size

    count_stmt = select(func.count()).select_from(BookmarkedIssue).where(
        BookmarkedIssue.user_id == user_id
    )
    count_result = await db.exec(count_stmt)
    total = count_result.one()

    list_stmt = (
        select(BookmarkedIssue, func.count(PersonalNote.id))
        .outerjoin(PersonalNote, BookmarkedIssue.id == PersonalNote.bookmark_id)
        .where(BookmarkedIssue.user_id == user_id)
        .group_by(BookmarkedIssue.id)
        .order_by(BookmarkedIssue.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.exec(list_stmt)
    rows = result.all()

    bookmarks = [
        BookmarkSchema(
            id=row[0].id,
            issue_node_id=row[0].issue_node_id,
            github_url=row[0].github_url,
            title_snapshot=row[0].title_snapshot,
            body_snapshot=row[0].body_snapshot,
            is_resolved=row[0].is_resolved,
            created_at=row[0].created_at,
            notes_count=row[1],
        )
        for row in rows
    ]

    has_more = (offset + len(bookmarks)) < total

    return bookmarks, total, has_more


async def get_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,

) -> BookmarkSchema | None:
    stmt = (
        select(BookmarkedIssue, func.count(PersonalNote.id))
        .outerjoin(PersonalNote, BookmarkedIssue.id == PersonalNote.bookmark_id)
        .where(
            BookmarkedIssue.id == bookmark_id,
            BookmarkedIssue.user_id == user_id,
        )
        .group_by(BookmarkedIssue.id)
    )
    result = await db.exec(stmt)
    row = result.first()

    if row is None:
        return None

    bookmark, count = row
    return BookmarkSchema(
        id=bookmark.id,
        issue_node_id=bookmark.issue_node_id,
        github_url=bookmark.github_url,
        title_snapshot=bookmark.title_snapshot,
        body_snapshot=bookmark.body_snapshot,
        is_resolved=bookmark.is_resolved,
        created_at=bookmark.created_at,
        notes_count=count,
    )



async def get_bookmark_with_notes_count(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
) -> tuple[BookmarkedIssue | None, int]:
    # Deprecated: usage should be replaced by get_bookmark which now includes count
    schema = await get_bookmark(db, user_id, bookmark_id)
    if schema is None:
        return None, 0
    # Temporary compatibility return
    # We construct a fake ORM object if really needed, but better to update callers?
    # Actually, let's update this to return the Schema directly or just remove it if callers are updated.
    # The integration plan says update 'bookmarks.py' to use shared models.
    # So we can remove this function if we update the route to use get_bookmark.
    # For now, let's make it return Schema since we're refactoring.
    return schema, schema.notes_count


async def update_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
    is_resolved: bool,

) -> BookmarkSchema | None:
    # We need the ORM object to update
    stmt = select(BookmarkedIssue).where(
        BookmarkedIssue.id == bookmark_id,
        BookmarkedIssue.user_id == user_id,
    )
    result = await db.exec(stmt)
    bookmark = result.first()

    if bookmark is None:
        return None

    bookmark.is_resolved = is_resolved

    await db.commit()
    await db.refresh(bookmark)

    # Return schema
    return await get_bookmark(db, user_id, bookmark_id)


async def delete_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
) -> bool:
    """Cascade deletes associated notes before removing bookmark."""
    # We need to find it first. get_bookmark returns schema now, so we need a separate check or custom query.
    stmt = select(BookmarkedIssue).where(
        BookmarkedIssue.id == bookmark_id,
        BookmarkedIssue.user_id == user_id,
    )
    result = await db.exec(stmt)
    bookmark = result.first()

    if bookmark is None:
        return False

    delete_notes_stmt = delete(PersonalNote).where(
        PersonalNote.bookmark_id == bookmark_id
    )
    await db.exec(delete_notes_stmt)

    db.delete(bookmark)
    await db.commit()

    logger.info(f"Deleted bookmark {bookmark_id} and associated notes for user {user_id}")
    return True


async def create_note(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
    content: str,

) -> NoteSchema | None:
    # ownership check
    bm_stmt = select(BookmarkedIssue).where(
        BookmarkedIssue.id == bookmark_id,
        BookmarkedIssue.user_id == user_id,
    )
    if (await db.exec(bm_stmt)).first() is None:
        return None

    note = PersonalNote(
        bookmark_id=bookmark_id,
        content=content,
    )

    db.add(note)
    await db.commit()
    await db.refresh(note)

    logger.info(f"Created note {note.id} on bookmark {bookmark_id}")
    return NoteSchema(
        id=note.id,
        bookmark_id=note.bookmark_id,
        content=note.content,
        updated_at=note.updated_at,
    )


async def list_notes(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,

) -> list[NoteSchema] | None:
    # ownership check
    bm_stmt = select(BookmarkedIssue).where(
        BookmarkedIssue.id == bookmark_id,
        BookmarkedIssue.user_id == user_id,
    )
    if (await db.exec(bm_stmt)).first() is None:
        return None

    stmt = (
        select(PersonalNote)
        .where(PersonalNote.bookmark_id == bookmark_id)
        .order_by(PersonalNote.updated_at.desc())
    )
    result = await db.exec(stmt)
    rows = result.all()

    return [
        NoteSchema(
            id=n.id,
            bookmark_id=n.bookmark_id,
            content=n.content,
            updated_at=n.updated_at,
        )
        for n in rows
    ]


async def get_note_with_ownership_check(
    db: AsyncSession,
    user_id: UUID,
    note_id: UUID,
) -> PersonalNote | None:
    """Verifies ownership via join to parent bookmark."""
    stmt = (
        select(PersonalNote)
        .join(BookmarkedIssue, PersonalNote.bookmark_id == BookmarkedIssue.id)
        .where(
            PersonalNote.id == note_id,
            BookmarkedIssue.user_id == user_id,
        )
    )
    result = await db.exec(stmt)
    return result.first()


async def update_note(
    db: AsyncSession,
    user_id: UUID,
    note_id: UUID,
    content: str,
) -> NoteSchema | None:
    # Need ORM object
    note = await get_note_with_ownership_check(db, user_id, note_id)
    if note is None:
        return None

    note.content = content
    note.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(note)

    logger.info(f"Updated note {note_id}")
    return NoteSchema(
        id=note.id,
        bookmark_id=note.bookmark_id,
        content=note.content,
        updated_at=note.updated_at,
    )


async def delete_note(
    db: AsyncSession,
    user_id: UUID,
    note_id: UUID,
) -> bool:
    note = await get_note_with_ownership_check(db, user_id, note_id)
    if note is None:
        return False

    db.delete(note)
    await db.commit()

    logger.info(f"Deleted note {note_id}")
    return True


async def get_notes_count_for_bookmark(
    db: AsyncSession,
    bookmark_id: UUID,
) -> int:
    stmt = select(func.count()).select_from(PersonalNote).where(
        PersonalNote.bookmark_id == bookmark_id
    )
    result = await db.exec(stmt)
    return result.one()


async def check_bookmark(
    db: AsyncSession,
    user_id: UUID,
    issue_node_id: str,
) -> tuple[bool, UUID | None]:
    """
    Checks if user has bookmarked a specific issue.

    Returns:
        (bookmarked: bool, bookmark_id: UUID | None)
    """
    stmt = select(BookmarkedIssue.id).where(
        BookmarkedIssue.user_id == user_id,
        BookmarkedIssue.issue_node_id == issue_node_id,
    )
    result = await db.exec(stmt)
    bookmark_id = result.first()

    if bookmark_id is not None:
        return True, bookmark_id
    return False, None


async def check_bookmarks_batch(
    db: AsyncSession,
    user_id: UUID,
    issue_node_ids: list[str],
) -> dict[str, UUID | None]:
    """
    Batch check if user has bookmarked multiple issues.
    Handles duplicates by deduping input.

    Args:
        issue_node_ids: List of issue node IDs (duplicates allowed, will be deduped)

    Returns:
        Dict mapping issue_node_id -> bookmark_id (or None if not bookmarked)
    """
    if not issue_node_ids:
        return {}

    # Dedupe input
    unique_ids = list(set(issue_node_ids))

    # Initialize result with None for all requested IDs
    result_map: dict[str, UUID | None] = {node_id: None for node_id in unique_ids}

    # Fetch all matching bookmarks in single query
    stmt = select(BookmarkedIssue.issue_node_id, BookmarkedIssue.id).where(
        BookmarkedIssue.user_id == user_id,
        BookmarkedIssue.issue_node_id.in_(unique_ids),
    )
    result = await db.exec(stmt)
    rows = result.all()

    # Update result map with found bookmarks
    for row in rows:
        result_map[row.issue_node_id] = row.id

    return result_map


__all__ = [
    "create_bookmark",
    "list_bookmarks",
    "get_bookmark",
    "get_bookmark_with_notes_count",
    "update_bookmark",
    "delete_bookmark",
    "create_note",
    "list_notes",
    "update_note",
    "delete_note",
    "get_notes_count_for_bookmark",
    "check_bookmark",
    "check_bookmarks_batch",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
]

