from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update

from app.core.db import async_session_maker
from app.models.time_entry import TimeEntry
from app.models.user import UserRole
from tests.conftest import make_user


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def period(days: int = 1) -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "start": (now - timedelta(days=days)).isoformat(),
        "end": (now + timedelta(days=days)).isoformat(),
    }


async def test_employee_clocks_in_and_out(anon_client: AsyncClient) -> None:
    auth = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))

    current = await anon_client.get("/time/me/current", headers=auth)
    assert current.status_code == 200
    assert current.json() is None

    clock_in = await anon_client.post("/time/me/clock-in", headers=auth)
    assert clock_in.status_code == 201
    entry = clock_in.json()
    assert entry["ended_at"] is None
    assert entry["user_email"] == "emp@exemple.cm"
    # Times come back with their zone so browsers show local time.
    assert entry["started_at"].endswith("Z") or entry["started_at"].endswith("+00:00")

    again = await anon_client.post("/time/me/clock-in", headers=auth)
    assert again.status_code == 409
    assert (await anon_client.get("/time/me/current", headers=auth)).json()["id"] == entry["id"]

    clock_out = await anon_client.post("/time/me/clock-out", headers=auth)
    assert clock_out.status_code == 200
    assert clock_out.json()["ended_at"] is not None
    assert (await anon_client.post("/time/me/clock-out", headers=auth)).status_code == 409

    mine = await anon_client.get("/time/me/entries", params=period(), headers=auth)
    assert [e["id"] for e in mine.json()] == [entry["id"]]


async def test_break_is_the_gap_between_entries(anon_client: AsyncClient) -> None:
    auth = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    for _ in range(2):
        await anon_client.post("/time/me/clock-in", headers=auth)
        await anon_client.post("/time/me/clock-out", headers=auth)
    entries = (await anon_client.get("/time/me/entries", params=period(), headers=auth)).json()
    assert len(entries) == 2
    assert all(e["ended_at"] for e in entries)


async def test_customers_cannot_clock_in(anon_client: AsyncClient) -> None:
    assert (await anon_client.post("/time/me/clock-in")).status_code == 401
    customer = bearer(await make_user("client@exemple.cm", "motdepasse"))
    assert (await anon_client.post("/time/me/clock-in", headers=customer)).status_code == 403
    assert (await anon_client.get("/time/me/current", headers=customer)).status_code == 403


async def test_admin_can_clock_in_too(client: AsyncClient) -> None:
    assert (await client.post("/time/me/clock-in")).status_code == 201


async def test_employees_only_see_their_own_entries(anon_client: AsyncClient) -> None:
    a = bearer(await make_user("a@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    b = bearer(await make_user("b@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    await anon_client.post("/time/me/clock-in", headers=a)
    await anon_client.post("/time/me/clock-in", headers=b)
    mine = (await anon_client.get("/time/me/entries", params=period(), headers=a)).json()
    assert [e["user_email"] for e in mine] == ["a@exemple.cm"]
    assert (await anon_client.get("/time/entries", params=period(), headers=a)).status_code == 403


async def test_period_filter_uses_start_time(anon_client: AsyncClient) -> None:
    auth = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    await anon_client.post("/time/me/clock-in", headers=auth)
    await anon_client.post("/time/me/clock-out", headers=auth)
    async with async_session_maker() as session:
        week_ago = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
        await session.execute(
            update(TimeEntry).values(started_at=week_ago, ended_at=week_ago + timedelta(hours=8))
        )
        await session.commit()
    today = (await anon_client.get("/time/me/entries", params=period(), headers=auth)).json()
    assert today == []
    month = (await anon_client.get("/time/me/entries", params=period(10), headers=auth)).json()
    assert len(month) == 1


async def test_admin_lists_and_corrects_entries(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    emp_token = await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE)
    entry = (await anon_client.post("/time/me/clock-in", headers=bearer(emp_token))).json()

    listed = await client.get("/time/entries", params=period())
    assert [e["id"] for e in listed.json()] == [entry["id"]]
    only = await client.get("/time/entries", params={**period(), "user_id": 999})
    assert only.json() == []

    fixed = await client.put(
        f"/time/entries/{entry['id']}",
        json={"started_at": "2026-10-20T07:00:00+01:00", "ended_at": "2026-10-20T16:30:00+01:00"},
    )
    assert fixed.status_code == 200
    body = fixed.json()
    assert body["started_at"].startswith("2026-10-20T06:00:00")  # stored as UTC
    assert body["edited_at"] is not None
    admin_id = (await client.get("/auth/me")).json()["id"]
    assert body["edited_by_id"] == admin_id

    backwards = await client.put(
        f"/time/entries/{entry['id']}",
        json={"started_at": "2026-10-20T16:00:00Z", "ended_at": "2026-10-20T08:00:00Z"},
    )
    assert backwards.status_code == 422
    assert (await client.put("/time/entries/999", json=body)).status_code == 404

    assert (await client.delete(f"/time/entries/{entry['id']}")).status_code == 204
    assert (await client.delete(f"/time/entries/{entry['id']}")).status_code == 404


async def test_correction_cannot_reopen_a_second_entry(
    client: AsyncClient, anon_client: AsyncClient
) -> None:
    auth = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    first = (await anon_client.post("/time/me/clock-in", headers=auth)).json()
    await anon_client.post("/time/me/clock-out", headers=auth)
    await anon_client.post("/time/me/clock-in", headers=auth)
    reopen = await client.put(
        f"/time/entries/{first['id']}", json={"started_at": first["started_at"], "ended_at": None}
    )
    assert reopen.status_code == 409


async def test_admin_assigns_employee_role(client: AsyncClient) -> None:
    await make_user("new@exemple.cm", "motdepasse")
    user_id = (await client.get("/users/")).json()[1]["id"]
    response = await client.patch(f"/users/{user_id}/role", json={"role": "employee"})
    assert response.status_code == 200
    assert response.json()["role"] == "employee"


async def test_manager_sees_and_corrects_others_but_not_own(anon_client: AsyncClient) -> None:
    emp = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    boss = bearer(await make_user("resp@exemple.cm", "motdepasse", UserRole.MANAGER))
    theirs = (await anon_client.post("/time/me/clock-in", headers=emp)).json()
    own = (await anon_client.post("/time/me/clock-in", headers=boss)).json()

    listed = await anon_client.get("/time/entries", params=period(), headers=boss)
    assert {e["id"] for e in listed.json()} == {theirs["id"], own["id"]}
    staff = await anon_client.get("/time/staff", headers=boss)
    assert [u["email"] for u in staff.json()] == ["emp@exemple.cm", "resp@exemple.cm"]

    fix = {"started_at": "2026-10-20T07:00:00Z", "ended_at": "2026-10-20T15:00:00Z"}
    ok = await anon_client.put(f"/time/entries/{theirs['id']}", json=fix, headers=boss)
    assert ok.status_code == 200
    mine = await anon_client.put(f"/time/entries/{own['id']}", json=fix, headers=boss)
    assert mine.status_code == 403
    deleted = await anon_client.delete(f"/time/entries/{own['id']}", headers=boss)
    assert deleted.status_code == 403


async def test_manager_has_no_admin_rights(anon_client: AsyncClient) -> None:
    boss = bearer(await make_user("resp@exemple.cm", "motdepasse", UserRole.MANAGER))
    assert (await anon_client.get("/users/", headers=boss)).status_code == 403
    emp = bearer(await make_user("emp@exemple.cm", "motdepasse", UserRole.EMPLOYEE))
    assert (await anon_client.get("/time/staff", headers=emp)).status_code == 403
