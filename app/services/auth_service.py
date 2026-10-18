from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    EmailAlreadyUsedError,
    InvalidCredentialsError,
    LastAdminError,
    UserNotFoundError,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from app.models.user import AuthToken, User, UserRole


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def register(self, email: str, password: str, role: UserRole = UserRole.USER) -> User:
        if await self.get_by_email(email) is not None:
            raise EmailAlreadyUsedError()
        user = User(email=normalize_email(email), password_hash=hash_password(password), role=role)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            # Two simultaneous sign-ups with the same e-mail: the unique index decides.
            await self.session.rollback()
            raise EmailAlreadyUsedError() from exc
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.get_by_email(email)
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)  # same timing as a wrong password
            raise InvalidCredentialsError()
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    async def create_token(self, user: User) -> str:
        token, token_hash = new_token()
        now = datetime.now()
        expires_at = now + timedelta(days=get_settings().token_ttl_days)
        # Drop this user's expired sessions while we are here.
        await self.session.execute(
            delete(AuthToken).where(AuthToken.user_id == user.id, AuthToken.expires_at < now)
        )
        self.session.add(AuthToken(token_hash=token_hash, user_id=user.id, expires_at=expires_at))
        await self.session.commit()
        return token

    async def user_for_token(self, token: str) -> User | None:
        auth = await self.session.get(AuthToken, hash_token(token))
        if auth is None or auth.expires_at < datetime.now():
            return None
        return auth.user

    async def revoke_token(self, token: str) -> None:
        await self.session.execute(
            delete(AuthToken).where(AuthToken.token_hash == hash_token(token))
        )
        await self.session.commit()

    async def list_users(self) -> Sequence[User]:
        result = await self.session.execute(select(User).order_by(User.created_at, User.id))
        return result.scalars().all()

    async def set_role(self, user_id: int, role: UserRole) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if user.role == UserRole.ADMIN and role != UserRole.ADMIN:
            admins = await self.session.scalar(
                select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
            )
            if (admins or 0) <= 1:
                raise LastAdminError()
        user.role = role
        await self.session.commit()
        await self.session.refresh(user)
        return user
