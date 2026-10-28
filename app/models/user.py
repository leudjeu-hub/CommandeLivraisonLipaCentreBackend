from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(enum.StrEnum):
    USER = "user"
    # Staff who clock in and out (see TimeEntry); administrators can clock in too.
    EMPLOYEE = "employee"
    # Supervises the time clock (sees and corrects employees' hours); no products or roles.
    MANAGER = "manager"
    ADMIN = "admin"


# Roles that clock in and out
STAFF_ROLES = (UserRole.EMPLOYEE, UserRole.MANAGER, UserRole.ADMIN)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stored lowercased (see AuthService) so the unique index is case-insensitive in practice.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=UserRole.USER,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    # A blocked account cannot log in and its sessions stop working.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    # Naive UTC time of the last successful login or sign-up (None: never since this was added).
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Administrators' internal remarks (Gestion > Utilisateurs); only /users returns them.
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthToken(Base):
    """A login session. Only the SHA-256 of the bearer token is stored."""

    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user: Mapped[User] = relationship(lazy="selectin")
