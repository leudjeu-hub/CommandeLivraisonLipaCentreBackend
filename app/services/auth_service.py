from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AccountBlockedError,
    EmailAlreadyUsedError,
    InvalidCredentialsError,
    LastAdminError,
    OwnAccountError,
    UserHasTimeEntriesError,
    UserNotFoundError,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from app.models.order import Order
from app.models.time_entry import TimeEntry
from app.models.user import STAFF_ROLES, AuthToken, User, UserRole


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
        # Checked after the password, so a wrong guess never learns that the account exists.
        if not user.is_active:
            raise AccountBlockedError()
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
        # A new session is a login (or a sign-up): the administrator sees it in the users list.
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()
        return token

    async def user_for_token(self, token: str) -> User | None:
        auth = await self.session.get(AuthToken, hash_token(token))
        if auth is None or auth.expires_at < datetime.now() or not auth.user.is_active:
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

    async def list_staff(self) -> Sequence[User]:
        result = await self.session.execute(
            select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.email)
        )
        return result.scalars().all()

    async def _get(self, user_id: int) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def _ensure_not_last_admin(self, user: User) -> None:
        """Refuse a change that would leave no active administrator."""
        if user.role != UserRole.ADMIN or not user.is_active:
            return
        admins = await self.session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        if (admins or 0) <= 1:
            raise LastAdminError()

    async def set_role(self, user_id: int, role: UserRole) -> User:
        user = await self._get(user_id)
        if role != UserRole.ADMIN:
            await self._ensure_not_last_admin(user)
        user.role = role
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def set_active(self, user_id: int, active: bool, actor: User) -> User:
        user = await self._get(user_id)
        if user.id == actor.id:
            raise OwnAccountError()
        if not active:
            await self._ensure_not_last_admin(user)
            await self.session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
        user.is_active = active
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int, actor: User) -> None:
        user = await self._get(user_id)
        if user.id == actor.id:
            raise OwnAccountError()
        await self._ensure_not_last_admin(user)
        # Deleting would erase the hours (cascade): keep the history, block the account instead.
        has_hours = await self.session.scalar(
            select(TimeEntry.id).where(TimeEntry.user_id == user.id).limit(1)
        )
        if has_hours is not None:
            raise UserHasTimeEntriesError()
        # The orders stay for the shop, without the account (SQLite does not apply ON DELETE)
        await self.session.execute(
            update(Order).where(Order.user_id == user.id).values(user_id=None)
        )
        await self.session.delete(user)
        await self.session.commit()
