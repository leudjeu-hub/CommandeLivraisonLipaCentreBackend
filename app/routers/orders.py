from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import OrderServiceDep, require_admin
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.order_service import to_order_read

router = APIRouter()

# Anyone can place an order (no account needed); reading orders exposes customers' names and
# phone numbers, so listing, reading and updating them is for administrators.
ADMIN_ONLY = [Depends(require_admin)]


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, service: OrderServiceDep) -> OrderRead:
    order = await service.create(data)
    return to_order_read(order)


@router.get("/", response_model=list[OrderRead], dependencies=ADMIN_ONLY)
async def list_orders(service: OrderServiceDep) -> list[OrderRead]:
    return [to_order_read(order) for order in await service.list()]


@router.get("/{order_id}", response_model=OrderRead, dependencies=ADMIN_ONLY)
async def get_order(order_id: int, service: OrderServiceDep) -> OrderRead:
    order = await service.get(order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order_read(order)


@router.patch("/{order_id}/status", response_model=OrderRead, dependencies=ADMIN_ONLY)
async def update_order_status(
    order_id: int, data: OrderStatusUpdate, service: OrderServiceDep
) -> OrderRead:
    order = await service.update_status(order_id, data)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order_read(order)
