from fastapi import APIRouter, Depends, status

from app.core.deps import AdminDep, AuthServiceDep, require_admin
from app.schemas.auth import ActiveUpdate, RoleUpdate, UserAdminRead

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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, admin: AdminDep, service: AuthServiceDep) -> None:
    """Delete an account, unless it has recorded hours (block it instead)."""
    await service.delete_user(user_id, admin)
