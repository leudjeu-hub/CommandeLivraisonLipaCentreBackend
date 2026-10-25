from fastapi import APIRouter, status

from app.core.deps import AuthServiceDep, CurrentUserDep, TokenDep
from app.core.exceptions import InvalidCredentialsError, TooManyAttemptsError
from app.core.rate_limit import ALL, login_throttle, register_throttle
from app.schemas.auth import Credentials, LoginRequest, TokenRead, UserRead
from app.services.auth_service import normalize_email

router = APIRouter()


@router.post("/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
async def register(data: Credentials, service: AuthServiceDep) -> TokenRead:
    """Create a customer account (role ``user``) and log it in. Site-wide limit: see rate_limit."""
    if register_throttle.is_blocked(ALL):
        raise TooManyAttemptsError()
    user = await service.register(data.email, data.password)
    register_throttle.record_failure(ALL)
    token = await service.create_token(user)
    return TokenRead(token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenRead)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenRead:
    """Log in. Too many wrong passwords for one e-mail get 429 for a while (password guessing)."""
    key = normalize_email(data.email)
    if login_throttle.is_blocked(key):
        raise TooManyAttemptsError()
    try:
        user = await service.authenticate(data.email, data.password)
    except InvalidCredentialsError:
        login_throttle.record_failure(key)
        raise
    login_throttle.reset(key)
    token = await service.create_token(user)
    return TokenRead(token=token, user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: TokenDep, service: AuthServiceDep) -> None:
    await service.revoke_token(token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(user)
