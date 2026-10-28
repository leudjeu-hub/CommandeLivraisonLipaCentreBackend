from fastapi import APIRouter, Depends, status

from app.core.deps import AdminDep, AuthServiceDep, require_admin
from app.schemas.auth import ActiveUpdate, RoleUpdate, TemporaryPassword, UserAdminRead
from app.schemas.order import AdminNotesUpdate

# Every route here is for administrators only.
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[UserAdminRead])
async def list_users(service: AuthServiceDep) -> list[UserAdminRead]:
    return [UserAdminRead.model_validate(u) for u in await service.list_users()]


@router.patch("/{user_id}/role", response_model=UserAdminRead)
async def update_role(user_id: int, data: RoleUpdate, service: AuthServiceDep) -> UserAdminRead:
    """Promote an account to administrator or demote it (the last admin cannot be demoted)."""
    return UserAdminRead.model_validate(await service.set_role(user_id, data.role))


@router.patch("/{user_id}/active", response_model=UserAdminRead)
async def set_active(
    user_id: int, data: ActiveUpdate, admin: AdminDep, service: AuthServiceDep
) -> UserAdminRead:
    """Block or unblock an account. Blocking ends its sessions; it keeps its data."""
    return UserAdminRead.model_validate(await service.set_active(user_id, data.active, admin))


@router.patch("/{user_id}/admin-notes", response_model=UserAdminRead)
async def update_admin_notes(
    user_id: int, data: AdminNotesUpdate, service: AuthServiceDep
) -> UserAdminRead:
    """Internal remarks on an account (empty clears them). The account's owner never sees them."""
    return UserAdminRead.model_validate(await service.set_admin_notes(user_id, data.admin_notes))


@router.post("/{user_id}/password", response_model=TemporaryPassword)
async def reset_password(
    user_id: int, admin: AdminDep, service: AuthServiceDep
) -> TemporaryPassword:
    """Forgotten password: a new random password, shown once to the admin. Ends its sessions."""
    return TemporaryPassword(password=await service.reset_password(user_id, admin))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, admin: AdminDep, service: AuthServiceDep) -> None:
    """Delete an account, unless it has recorded hours (block it instead)."""
    await service.delete_user(user_id, admin)
