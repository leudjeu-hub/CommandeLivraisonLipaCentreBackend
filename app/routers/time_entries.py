from datetime import datetime

from fastapi import APIRouter, Query, status

from app.core.deps import AdminDep, StaffDep, TimeServiceDep
from app.schemas.time_entry import TimeEntryRead, TimeEntryUpdate, _to_naive_utc
from app.services.time_service import to_time_entry_read

router = APIRouter()

# Periods are [start, end) and should carry a time zone (the site sends the shop's local
# midnight); times without one are taken as UTC. An entry belongs to the period it started in.
Start = Query(description="Start of the period (inclusive)")
End = Query(description="End of the period (exclusive)")


def _period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    return _to_naive_utc(start) or start, _to_naive_utc(end) or end


@router.get("/me/current", response_model=TimeEntryRead | None)
async def current_entry(user: StaffDep, service: TimeServiceDep) -> TimeEntryRead | None:
    """The open entry of the signed-in employee, or null when they are not clocked in."""
    entry = await service.open_entry(user.id)
    return to_time_entry_read(entry) if entry else None


@router.post("/me/clock-in", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
async def clock_in(user: StaffDep, service: TimeServiceDep) -> TimeEntryRead:
    return to_time_entry_read(await service.clock_in(user))


@router.post("/me/clock-out", response_model=TimeEntryRead)
async def clock_out(user: StaffDep, service: TimeServiceDep) -> TimeEntryRead:
    return to_time_entry_read(await service.clock_out(user))


@router.get("/me/entries", response_model=list[TimeEntryRead])
async def my_entries(
    user: StaffDep,
    service: TimeServiceDep,
    start: datetime = Start,
    end: datetime = End,
) -> list[TimeEntryRead]:
    entries = await service.list(*_period(start, end), user_id=user.id)
    return [to_time_entry_read(e) for e in entries]


@router.get("/entries", response_model=list[TimeEntryRead])
async def all_entries(
    _: AdminDep,
    service: TimeServiceDep,
    start: datetime = Start,
    end: datetime = End,
    user_id: int | None = None,
) -> list[TimeEntryRead]:
    entries = await service.list(*_period(start, end), user_id=user_id)
    return [to_time_entry_read(e) for e in entries]


@router.put("/entries/{entry_id}", response_model=TimeEntryRead)
async def correct_entry(
    entry_id: int, data: TimeEntryUpdate, admin: AdminDep, service: TimeServiceDep
) -> TimeEntryRead:
    """Fix a forgotten or wrong punch. The correction is stamped with who made it and when."""
    return to_time_entry_read(await service.correct(entry_id, data, admin))


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, _: AdminDep, service: TimeServiceDep) -> None:
    await service.delete(entry_id)
