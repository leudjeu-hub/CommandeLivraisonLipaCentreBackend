from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _as_utc(value: datetime | None) -> datetime | None:
    """Stored times are naive UTC: say so, so browsers convert them to local time."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


class TimeEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_email: str
    started_at: datetime
    ended_at: datetime | None
    edited_at: datetime | None
    edited_by_id: int | None

    _utc = field_validator("started_at", "ended_at", "edited_at")(_as_utc)


class TimeEntryUpdate(BaseModel):
    """An administrator's correction. Times without a time zone are taken as UTC."""

    started_at: datetime
    ended_at: datetime | None = None

    _naive = field_validator("started_at", "ended_at")(_to_naive_utc)

    @model_validator(mode="after")
    def _ends_after_start(self) -> "TimeEntryUpdate":
        if self.ended_at is not None and self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self
