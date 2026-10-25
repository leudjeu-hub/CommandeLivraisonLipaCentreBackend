"""Forgotten password: a single-use link sent by e-mail.

The link carries a random token (only its SHA-256 is stored) that expires after
``PASSWORD_RESET_TTL_MINUTES``. Requesting a new link cancels the previous one; using it sets the
new password and ends every open session of the account.
"""

from datetime import datetime, timedelta
from html import escape

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidResetTokenError
from app.core.security import hash_password, hash_token, new_token
from app.models.user import AuthToken, PasswordResetToken, User
from app.services.auth_service import AuthService
from app.services.mailer import send_email


def reset_link(token: str) -> str:
    # In the fragment, not the query: browsers never send it to a server (GitHub Pages logs,
    # Referer headers).
    return f"{get_settings().site_url.rstrip('/')}/mot-de-passe/nouveau#token={token}"


def reset_email(link: str, minutes: int) -> tuple[str, str, str]:
    """Return ``(subject, text, html)``."""
    subject = "Réinitialiser votre mot de passe LipaCentre"
    text = (
        "Bonjour,\n\n"
        "Vous avez demandé à changer le mot de passe de votre compte LipaCentre.\n"
        f"Ouvrez ce lien pour choisir un nouveau mot de passe (valable {minutes} minutes, "
        "une seule fois) :\n\n"
        f"{link}\n\n"
        "Si vous n'avez rien demandé, ignorez ce message : votre mot de passe ne change pas.\n\n"
        "LipaCentre"
    )
    url = escape(link)
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#16325c;max-width:520px">'
        "<p>Bonjour,</p>"
        "<p>Vous avez demandé à changer le mot de passe de votre compte LipaCentre.</p>"
        f'<p><a href="{url}" style="display:inline-block;background:#16325c;color:#fff;'
        'padding:12px 20px;border-radius:6px;text-decoration:none">'
        "Choisir un nouveau mot de passe</a></p>"
        f"<p>Ce lien est valable {minutes} minutes et ne sert qu'une fois. "
        f"S'il ne s'ouvre pas, copiez cette adresse dans votre navigateur :<br>{url}</p>"
        "<p>Si vous n'avez rien demandé, ignorez ce message : votre mot de passe ne change pas.</p>"
        "<p>LipaCentre</p></div>"
    )
    return subject, text, html


class PasswordResetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_token(self, user: User) -> str:
        token, token_hash = new_token()
        minutes = get_settings().password_reset_ttl_minutes
        # One valid link at a time: the newest one.
        await self.session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        self.session.add(
            PasswordResetToken(
                token_hash=token_hash,
                user_id=user.id,
                expires_at=datetime.now() + timedelta(minutes=minutes),
            )
        )
        await self.session.commit()
        return token

    async def send_link(self, email: str) -> bool:
        """E-mail a reset link if an active account has this e-mail; otherwise do nothing."""
        user = await AuthService(self.session).get_by_email(email)
        if user is None or not user.is_active:
            return False
        token = await self.create_token(user)
        subject, text, html = reset_email(
            reset_link(token), get_settings().password_reset_ttl_minutes
        )
        return await send_email(user.email, subject, text, html)

    async def reset_password(self, token: str, password: str) -> User:
        reset = await self.session.get(PasswordResetToken, hash_token(token))
        if reset is None:
            raise InvalidResetTokenError()
        user = reset.user
        if reset.expires_at < datetime.now() or not user.is_active:
            await self.session.delete(reset)
            await self.session.commit()
            raise InvalidResetTokenError()
        user.password_hash = hash_password(password)
        # Single use, and whoever knew the old password is logged out everywhere.
        await self.session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        await self.session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
        await self.session.commit()
        return user
