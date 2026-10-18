from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientStockError,
    PriceOnRequestError,
    ProductNotFoundError,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.utils.whatsapp import build_whatsapp_link


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: OrderCreate) -> Order:
        order = Order(customer_name=data.customer_name, phone=data.phone)
        total = 0.0
        for item in data.items:
            product = await self.session.get(Product, item.product_id)
            if product is None:
                raise ProductNotFoundError(item.product_id)
            if product.price is None:
                raise PriceOnRequestError(product.name)
            if product.stock < item.quantity:
                raise InsufficientStockError(product.name)
            product.stock -= item.quantity
            total += product.price * item.quantity
            order.items.append(
                OrderItem(
                    product=product,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )
        order.total = total
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def list(self) -> Sequence[Order]:
        result = await self.session.execute(select(Order).order_by(Order.created_at.desc()))
        return result.scalars().all()

    async def get(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def update_status(self, order_id: int, data: OrderStatusUpdate) -> Order | None:
        order = await self.get(order_id)
        if order is None:
            return None
        order.status = data.status
        await self.session.commit()
        await self.session.refresh(order)
        return order


def to_order_read(order: Order) -> OrderRead:
    read = OrderRead.model_validate(order)
    read.whatsapp_url = build_whatsapp_link(order)
    return read
