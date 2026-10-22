from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyClockedInError, NotClockedInError, TimeEntryNotFoundError
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import TimeEntryRead, TimeEntryUpdate


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def to_time_entry_read(entry: TimeEntry) -> TimeEntryRead:
    return TimeEntryRead.model_validate(
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "user_email": entry.user.email,
            "started_at": entry.started_at,
            "ended_at": entry.ended_at,
            "edited_at": entry.edited_at,
            "edited_by_id": entry.edited_by_id,
        }
    )


class TimeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def open_entry(self, user_id: int) -> TimeEntry | None:
        result = await self.session.execute(
            select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None))
        )
        return result.scalars().first()

    async def clock_in(self, user: User) -> TimeEntry:
        if await self.open_entry(user.id) is not None:
            raise AlreadyClockedInError()
        entry = TimeEntry(user_id=user.id, started_at=utcnow())
        self.session.add(entry)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            # A double tap can race the check above; the partial unique index decides.
            await self.session.rollback()
            raise AlreadyClockedInError() from exc
        await self.session.refresh(entry)
        return entry

    async def clock_out(self, user: User) -> TimeEntry:
        entry = await self.open_entry(user.id)
        if entry is None:
            raise NotClockedInError()
        entry.ended_at = utcnow()
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def list(
        self, start: datetime, end: datetime, user_id: int | None = None
    ) -> Sequence[TimeEntry]:
        """Entries that started in [start, end), oldest first. Times are naive UTC."""
        query = select(TimeEntry).where(TimeEntry.started_at >= start, TimeEntry.started_at < end)
        if user_id is not None:
            query = query.where(TimeEntry.user_id == user_id)
        result = await self.session.execute(query.order_by(TimeEntry.started_at, TimeEntry.id))
        return result.scalars().all()

    async def correct(self, entry_id: int, data: TimeEntryUpdate, editor: User) -> TimeEntry:
        entry = await self.session.get(TimeEntry, entry_id)
        if entry is None:
            raise TimeEntryNotFoundError(entry_id)
        if data.ended_at is None and entry.ended_at is not None:
            other = await self.open_entry(entry.user_id)
            if other is not None and other.id != entry.id:
                raise AlreadyClockedInError()
        entry.started_at = data.started_at
        entry.ended_at = data.ended_at
        entry.edited_at = utcnow()
        entry.edited_by_id = editor.id
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def delete(self, entry_id: int) -> None:
        entry = await self.session.get(TimeEntry, entry_id)
        if entry is None:
            raise TimeEntryNotFoundError(entry_id)
        await self.session.delete(entry)
        await self.session.commit()
