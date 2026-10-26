from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientStockError,
    PriceOnRequestError,
    ProductNotFoundError,
)
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate, OrderSubmit
from app.utils.whatsapp import build_whatsapp_link

# Cancelled and delivered orders are deleted this long after their last status change, as the
# site's privacy page (/confidentialite) promises. Render's free plan has no scheduler: the purge
# runs whenever an administrator lists the orders.
RETENTION = {
    OrderStatus.CANCELLED: timedelta(days=30),
    OrderStatus.DELIVERED: timedelta(days=365),
}


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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

    async def submit(self, data: OrderSubmit) -> Order:
        """Record an order or quote sent by the site, at catalogue prices, without taking stock."""
        order = Order(
            kind=data.kind,
            customer_name=data.customer_name.strip(),
            phone=data.phone.strip(),
            area=data.area.strip() or None,
            address=data.address.strip() or None,
            slot=data.slot.strip() or None,
            payment=data.payment.strip() or None,
            notes=data.notes.strip() or None,
            delivery_fee=data.delivery_fee,
        )
        total = 0.0
        for item in data.items:
            product = await self.session.get(Product, item.product_id)
            if product is None:
                raise ProductNotFoundError(item.product_id)
            # Price on request: kept at 0, the shop quotes it
            price = product.price or 0.0
            total += price * item.quantity
            order.items.append(OrderItem(product=product, quantity=item.quantity, unit_price=price))
        order.total = total
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def purge_expired(self) -> int:
        """Delete orders kept longer than RETENTION allows for their status; returns how many."""
        now = utcnow()
        # Changed before status_changed_at existed: count from the order's creation
        changed = func.coalesce(Order.status_changed_at, Order.created_at)
        condition = or_(
            *(
                and_(Order.status == status, changed < now - keep)
                for status, keep in RETENTION.items()
            )
        )
        result = await self.session.execute(select(Order).where(condition))
        orders = result.scalars().all()
        for order in orders:
            await self.session.delete(order)
        if orders:
            await self.session.commit()
        return len(orders)

    async def list(self, status: OrderStatus | None = None) -> Sequence[Order]:
        await self.purge_expired()
        query = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
        if status is not None:
            query = query.where(Order.status == status)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def update_status(self, order_id: int, data: OrderStatusUpdate) -> Order | None:
        order = await self.get(order_id)
        if order is None:
            return None
        if order.status != data.status:
            order.status = data.status
            order.status_changed_at = utcnow()
        await self.session.commit()
        await self.session.refresh(order)
        return order


def to_order_read(order: Order) -> OrderRead:
    read = OrderRead.model_validate(order)
    read.whatsapp_url = build_whatsapp_link(order)
    return read
