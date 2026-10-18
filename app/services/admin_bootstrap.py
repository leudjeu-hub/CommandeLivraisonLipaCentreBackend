from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.auth import Credentials
from app.services.auth_service import AuthService


async def ensure_admin(session: AsyncSession, email: str, password: str) -> str | None:
    """Create the first administrator from ADMIN_EMAIL / ADMIN_PASSWORD.

    Does nothing once any administrator exists, so the variables can stay set (or be removed)
    without resetting a password changed later. An existing account with that e-mail is
    promoted and keeps its own password. Returns a message when something was done.
    """
    if await session.scalar(select(exists().where(User.role == UserRole.ADMIN))):
        return None
    service = AuthService(session)
    user = await service.get_by_email(email)
    if user is not None:
        await service.set_role(user.id, UserRole.ADMIN)
        return f"Existing account {user.email} promoted to administrator"
    # Same rules as sign-up (valid e-mail, 8+ characters); raises ValidationError (a ValueError).
    credentials = Credentials(email=email, password=password)
    user = await service.register(credentials.email, credentials.password, UserRole.ADMIN)
    return f"Administrator {user.email} created"
