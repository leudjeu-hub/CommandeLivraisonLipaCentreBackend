from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem


class OrderStatus(enum.StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderKind(enum.StrEnum):
    ORDER = "order"
    QUOTE = "quote"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            native_enum=False,
            length=20,
            # Store the values ('new'), as the migrations' CHECK constraints expect, not the names
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=OrderStatus.NEW,
    )
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # Filled by the site's order form (POST /orders/submit); empty for orders entered by an admin
    kind: Mapped[OrderKind] = mapped_column(
        Enum(
            OrderKind,
            native_enum=False,
            length=10,
            # Store the values ('new'), as the migrations' CHECK constraints expect, not the names
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=OrderKind.ORDER,
        server_default=OrderKind.ORDER.value,
    )
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    slot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # As shown to the customer by the site (zone rules live there); None = to be agreed
    delivery_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
