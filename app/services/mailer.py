"""Outgoing e-mail through Brevo's transactional HTTP API.

Render's free plan blocks outbound SMTP (ports 25, 465, 587), so Gmail's SMTP server cannot be
used from there; Brevo's free plan sends 300 e-mails a day over HTTPS. Without ``BREVO_API_KEY``
nothing is sent and a warning is logged (local development, tests).
"""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    """Send one e-mail; return whether it was accepted. Never raises: callers run in the
    background and the user already got their answer."""
    settings = get_settings()
    if settings.brevo_api_key is None:
        logger.warning("E-mail to %s not sent: BREVO_API_KEY is not set", to)
        return False
    payload = {
        "sender": {"email": settings.mail_from, "name": settings.mail_from_name},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
        "htmlContent": html,
    }
    headers = {"api-key": settings.brevo_api_key.get_secret_value(), "accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(BREVO_URL, json=payload, headers=headers)
    except httpx.HTTPError:
        logger.exception("E-mail to %s not sent: Brevo unreachable", to)
        return False
    if response.status_code >= 400:
        logger.error(
            "E-mail to %s refused by Brevo (%s): %s", to, response.status_code, response.text
        )
        return False
    return True
