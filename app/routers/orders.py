from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import (
    CurrentUserDep,
    OptionalUserDep,
    OrderServiceDep,
    require_admin,
    require_manager,
)
from app.core.exceptions import TooManyOrdersError
from app.core.rate_limit import ALL, order_throttle
from app.models.order import OrderStatus
from app.schemas.order import (
    AdminNotesUpdate,
    OrderAdminRead,
    OrderClaim,
    OrderClaimResult,
    OrderCreate,
    OrderRead,
    OrderStatusUpdate,
    OrderSubmit,
)
from app.services.order_service import to_order_admin_read, to_order_read

router = APIRouter()

# Orders hold customers' names and phone numbers: managers and administrators read them and
# change their status; POST / takes stock, so it stays admin-only; POST /submit (the site's
# form) is public; GET /mine gives a logged-in customer their own orders, and only theirs.
# Staff routes answer with OrderAdminRead (internal remarks); customers' routes never do.
ADMIN_ONLY = [Depends(require_admin)]
MANAGERS = [Depends(require_manager)]


@router.post("/submit", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def submit_order(
    data: OrderSubmit, service: OrderServiceDep, user: OptionalUserDep
) -> OrderRead:
    """Public: the site records each order or quote request here before the customer sends it
    by WhatsApp or e-mail. No stock is taken; a site-wide limit keeps scripts from flooding it.
    Sent with a valid token, the order is linked to that account; an invalid one is ignored, so
    the order is never lost."""
    if order_throttle.is_blocked(ALL):
        raise TooManyOrdersError()
    order_throttle.record_failure(ALL)
    order, code = await service.submit(data, user.id if user else None)
    read = to_order_read(order)
    read.claim_code = code
    return read


@router.post("/claim", response_model=OrderClaimResult)
async def claim_orders(
    data: OrderClaim, user: CurrentUserDep, service: OrderServiceDep
) -> OrderClaimResult:
    """A customer who ordered as a guest, then logged in: the browser sends the codes it got from
    POST /submit, and those orders join the account (GET /mine). Without the code, no one can
    attach an order: a name or phone number is never enough."""
    return OrderClaimResult(claimed=await service.claim(data.codes, user.id))


@router.post(
    "/",
    response_model=OrderAdminRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=ADMIN_ONLY,
)
async def create_order(data: OrderCreate, service: OrderServiceDep) -> OrderAdminRead:
    order = await service.create(data)
    return to_order_admin_read(order)


@router.get("/", response_model=list[OrderAdminRead], dependencies=MANAGERS)
async def list_orders(
    service: OrderServiceDep, status: OrderStatus | None = None
) -> list[OrderAdminRead]:
    return [to_order_admin_read(order) for order in await service.list(status)]


@router.get("/mine", response_model=list[OrderRead])
async def my_orders(user: CurrentUserDep, service: OrderServiceDep) -> list[OrderRead]:
    """Any logged-in account: the orders it sent, never anyone else's (filtered on the token's
    user, not on a name or phone number the customer could type)."""
    return [to_order_read(order) for order in await service.list_for_user(user.id)]


@router.get("/{order_id}", response_model=OrderAdminRead, dependencies=MANAGERS)
async def get_order(order_id: int, service: OrderServiceDep) -> OrderAdminRead:
    order = await service.get(order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order_admin_read(order)


@router.patch("/{order_id}/status", response_model=OrderAdminRead, dependencies=MANAGERS)
async def update_order_status(
    order_id: int, data: OrderStatusUpdate, service: OrderServiceDep
) -> OrderAdminRead:
    order = await service.update_status(order_id, data)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order_admin_read(order)


@router.patch("/{order_id}/admin-notes", response_model=OrderAdminRead, dependencies=MANAGERS)
async def update_order_admin_notes(
    order_id: int, data: AdminNotesUpdate, service: OrderServiceDep
) -> OrderAdminRead:
    """The shop's internal remarks on an order (empty clears them). Never shown to the customer."""
    order = await service.set_admin_notes(order_id, data.admin_notes)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order_admin_read(order)
