from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.models.user import STAFF_ROLES, User, UserRole
from app.services.auth_service import AuthService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.time_service import TimeService

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def get_product_service(session: SessionDep) -> ProductService:
    return ProductService(session)


async def get_order_service(session: SessionDep) -> OrderService:
    return OrderService(session)


async def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(session)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]


async def get_time_service(session: SessionDep) -> TimeService:
    return TimeService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TimeServiceDep = Annotated[TimeService, Depends(get_time_service)]

# auto_error=False: a missing header gets our 401 (with WWW-Authenticate) instead of a 403.
bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_token(credentials: BearerDep) -> str:
    if credentials is None:
        raise _unauthorized()
    return credentials.credentials


TokenDep = Annotated[str, Depends(get_token)]


async def get_current_user(token: TokenDep, service: AuthServiceDep) -> User:
    user = await service.user_for_token(token)
    if user is None:
        raise _unauthorized()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUserDep) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


async def require_staff(user: CurrentUserDep) -> User:
    """Employees, managers and administrators: the people who clock in and out."""
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access required")
    return user


async def require_manager(user: CurrentUserDep) -> User:
    """Managers and administrators: the people who see and correct everyone's hours."""
    if user.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager access required")
    return user


StaffDep = Annotated[User, Depends(require_staff)]
ManagerDep = Annotated[User, Depends(require_manager)]
AdminDep = Annotated[User, Depends(require_admin)]
