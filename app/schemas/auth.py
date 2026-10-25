from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class Credentials(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    # No length rule here: a wrong password must get the same 401 as an unknown e-mail.
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    created_at: datetime
    is_active: bool


class UserAdminRead(UserRead):
    """What administrators see in the users list."""

    last_login_at: datetime | None

    @field_validator("last_login_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        """Stored times are naive UTC: say so, so browsers convert them to local time."""
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class TokenRead(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserRead


class RoleUpdate(BaseModel):
    role: UserRole


class ActiveUpdate(BaseModel):
    active: bool
