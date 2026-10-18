from fastapi import APIRouter, Depends

from app.core.deps import AuthServiceDep, require_admin
from app.schemas.auth import RoleUpdate, UserRead

# Every route here is for administrators only.
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[UserRead])
async def list_users(service: AuthServiceDep) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in await service.list_users()]


@router.patch("/{user_id}/role", response_model=UserRead)
async def update_role(user_id: int, data: RoleUpdate, service: AuthServiceDep) -> UserRead:
    """Promote an account to administrator or demote it (the last admin cannot be demoted)."""
    return UserRead.model_validate(await service.set_role(user_id, data.role))
