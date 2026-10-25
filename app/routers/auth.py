from fastapi import APIRouter, BackgroundTasks, status

from app.core.db import async_session_maker
from app.core.deps import AuthServiceDep, CurrentUserDep, SessionDep, TokenDep
from app.core.exceptions import InvalidCredentialsError, TooManyAttemptsError
from app.core.rate_limit import (
    ALL,
    login_throttle,
    register_throttle,
    reset_email_throttle,
    reset_throttle,
)
from app.schemas.auth import (
    Credentials,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenRead,
    UserRead,
)
from app.services.auth_service import normalize_email
from app.services.password_reset import PasswordResetService

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


async def _send_reset_link(email: str) -> None:
    async with async_session_maker() as session:
        await PasswordResetService(session).send_link(email)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    data: PasswordResetRequest, background: BackgroundTasks
) -> dict[str, str]:
    """E-mail a single-use link to choose a new password.

    The answer is the same whether or not an account exists, and the lookup and the e-mail happen
    after it is sent, so neither the answer nor its timing tells who has an account.
    """
    if reset_throttle.is_blocked(ALL):
        raise TooManyAttemptsError()
    key = normalize_email(data.email)
    if key and not reset_email_throttle.is_blocked(key):
        reset_email_throttle.record_failure(key)
        reset_throttle.record_failure(ALL)
        background.add_task(_send_reset_link, key)
    return {"detail": "If an account exists for this e-mail, a link has been sent"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(data: PasswordResetConfirm, session: SessionDep) -> None:
    """Set a new password with the e-mailed token. Every session of the account is closed; the
    person then logs in with the new password."""
    user = await PasswordResetService(session).reset_password(data.token, data.password)
    login_throttle.reset(user.email)
