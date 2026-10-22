from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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


class TokenRead(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserRead


class RoleUpdate(BaseModel):
    role: UserRole


class ActiveUpdate(BaseModel):
    active: bool
