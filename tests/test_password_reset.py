from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.db import async_session_maker
from app.core.rate_limit import MAX_FAILURES, MAX_RESETS, MAX_RESETS_PER_EMAIL, login_throttle
from app.models.user import PasswordResetToken, User
from app.services import password_reset
from tests.conftest import make_user


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """E-mails "sent" during the test, instead of calling Brevo."""
    sent: list[dict[str, str]] = []

    async def fake_send(to: str, subject: str, text: str, html: str) -> bool:
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(password_reset, "send_email", fake_send)
    return sent


def token_from(mail: dict[str, str]) -> str:
    return mail["text"].split("#token=")[1].split()[0]


async def request_reset(client: AsyncClient, email: str) -> None:
    response = await client.post("/auth/password-reset/request", json={"email": email})
    assert response.status_code == 202


async def reset_count() -> int:
    async with async_session_maker() as session:
        return await session.scalar(select(func.count()).select_from(PasswordResetToken)) or 0


async def test_reset_flow_sets_password_and_ends_sessions(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    old_session = await make_user("client@exemple.cm", "ancien-mdp")
    await request_reset(anon_client, " Client@Exemple.CM ")

    assert len(outbox) == 1
    mail = outbox[0]
    assert mail["to"] == "client@exemple.cm"
    assert (
        "https://leudjeu-hub.github.io/CommandeLivraisonLipaCentre/mot-de-passe/nouveau#token="
        in mail["text"]
    )
    token = token_from(mail)
    assert token in mail["html"]

    confirm = await anon_client.post(
        "/auth/password-reset/confirm", json={"token": token, "password": "nouveau-mdp"}
    )
    assert confirm.status_code == 204

    me = await anon_client.get("/auth/me", headers={"Authorization": f"Bearer {old_session}"})
    assert me.status_code == 401
    old = await anon_client.post(
        "/auth/login", json={"email": "client@exemple.cm", "password": "ancien-mdp"}
    )
    assert old.status_code == 401
    new = await anon_client.post(
        "/auth/login", json={"email": "client@exemple.cm", "password": "nouveau-mdp"}
    )
    assert new.status_code == 200

    # Single use
    again = await anon_client.post(
        "/auth/password-reset/confirm", json={"token": token, "password": "troisieme"}
    )
    assert again.status_code == 400
    assert await reset_count() == 0


async def test_unknown_or_blocked_email_gets_same_answer_and_no_mail(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("bloque@exemple.cm", "motdepasse")
    async with async_session_maker() as session:
        await session.execute(update(User).values(is_active=False))
        await session.commit()

    known = await anon_client.post(
        "/auth/password-reset/request", json={"email": "bloque@exemple.cm"}
    )
    unknown = await anon_client.post(
        "/auth/password-reset/request", json={"email": "personne@exemple.cm"}
    )
    garbage = await anon_client.post("/auth/password-reset/request", json={"email": "pas un mail"})
    assert known.status_code == unknown.status_code == garbage.status_code == 202
    assert known.json() == unknown.json() == garbage.json()
    assert outbox == []
    assert await reset_count() == 0


async def test_new_link_cancels_previous_one(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("client@exemple.cm", "ancien-mdp")
    await request_reset(anon_client, "client@exemple.cm")
    await request_reset(anon_client, "client@exemple.cm")
    first, second = token_from(outbox[0]), token_from(outbox[1])
    assert await reset_count() == 1

    stale = await anon_client.post(
        "/auth/password-reset/confirm", json={"token": first, "password": "nouveau-mdp"}
    )
    assert stale.status_code == 400
    ok = await anon_client.post(
        "/auth/password-reset/confirm", json={"token": second, "password": "nouveau-mdp"}
    )
    assert ok.status_code == 204


async def test_expired_link_is_refused(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("client@exemple.cm", "ancien-mdp")
    await request_reset(anon_client, "client@exemple.cm")
    async with async_session_maker() as session:
        await session.execute(
            update(PasswordResetToken).values(expires_at=datetime.now() - timedelta(minutes=1))
        )
        await session.commit()

    response = await anon_client.post(
        "/auth/password-reset/confirm",
        json={"token": token_from(outbox[0]), "password": "nouveau-mdp"},
    )
    assert response.status_code == 400
    assert await reset_count() == 0
    login = await anon_client.post(
        "/auth/login", json={"email": "client@exemple.cm", "password": "ancien-mdp"}
    )
    assert login.status_code == 200


async def test_confirm_rejects_short_password_and_keeps_link(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("client@exemple.cm", "ancien-mdp")
    await request_reset(anon_client, "client@exemple.cm")
    response = await anon_client.post(
        "/auth/password-reset/confirm", json={"token": token_from(outbox[0]), "password": "court"}
    )
    assert response.status_code == 422
    assert await reset_count() == 1


async def test_reset_clears_login_lockout(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("client@exemple.cm", "ancien-mdp")
    for _ in range(MAX_FAILURES):
        login_throttle.record_failure("client@exemple.cm")
    await request_reset(anon_client, "client@exemple.cm")
    await anon_client.post(
        "/auth/password-reset/confirm",
        json={"token": token_from(outbox[0]), "password": "nouveau-mdp"},
    )
    login = await anon_client.post(
        "/auth/login", json={"email": "client@exemple.cm", "password": "nouveau-mdp"}
    )
    assert login.status_code == 200


async def test_requests_are_throttled(
    anon_client: AsyncClient, outbox: list[dict[str, str]]
) -> None:
    await make_user("client@exemple.cm", "ancien-mdp")
    for _ in range(MAX_RESETS_PER_EMAIL + 2):
        await request_reset(anon_client, "client@exemple.cm")
    # Extra requests for one address are dropped silently (same answer, no e-mail).
    assert len(outbox) == MAX_RESETS_PER_EMAIL

    for i in range(MAX_RESETS):
        await anon_client.post("/auth/password-reset/request", json={"email": f"x{i}@exemple.cm"})
    blocked = await anon_client.post(
        "/auth/password-reset/request", json={"email": "autre@exemple.cm"}
    )
    assert blocked.status_code == 429


async def test_mailer_without_key_sends_nothing() -> None:
    from app.services.mailer import send_email

    assert await send_email("a@exemple.cm", "s", "t", "<p>h</p>") is False
