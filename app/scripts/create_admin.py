"""Create an administrator account, or promote an existing account to administrator.

Usage: uv run python -m app.scripts.create_admin admin@example.com

The password is asked interactively (or read from ADMIN_PASSWORD, e.g. on a server). An existing
account keeps its password and only gets the admin role. Further admins can then be promoted
from the site by an administrator (PATCH /users/{id}/role).
"""

import asyncio
import getpass
import os
import sys

from pydantic import ValidationError

from app.core.db import async_session_maker, engine
from app.models.user import UserRole
from app.schemas.auth import Credentials
from app.services.auth_service import AuthService


def read_password() -> str:
    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Password (8 characters min.): ")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    return password


async def create_admin(email: str, password: str | None) -> str:
    async with async_session_maker() as session:
        service = AuthService(session)
        user = await service.get_by_email(email)
        if user is not None:
            await service.set_role(user.id, UserRole.ADMIN)
            return f"{user.email} is now an administrator (password unchanged)."
        if password is None:
            raise ValueError("password required for a new account")
        credentials = Credentials(email=email, password=password)
        user = await service.register(credentials.email, credentials.password, UserRole.ADMIN)
        return f"Administrator {user.email} created."


async def _run(email: str) -> None:
    try:
        async with async_session_maker() as session:
            exists = await AuthService(session).get_by_email(email) is not None
        message = await create_admin(email, None if exists else read_password())
    except ValidationError as exc:
        sys.exit("; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors()))
    finally:
        await engine.dispose()
    print(message)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
