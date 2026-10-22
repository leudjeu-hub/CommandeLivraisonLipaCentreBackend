from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import User


class TimeEntry(Base):
    """One stretch of work, from clocking in to clocking out.

    Times are naive UTC, set by the server (never by the employee's device). A break is the gap
    between two entries, so it is never counted. ``ended_at`` is NULL while the employee is in.
    """

    __tablename__ = "time_entries"
    # At most one open entry per person, even if "clock in" is tapped twice at once.
    __table_args__ = (
        Index(
            "ux_time_entries_open",
            "user_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Set when an administrator corrects the times, so corrections stay visible.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="selectin")
