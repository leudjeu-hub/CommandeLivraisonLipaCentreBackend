from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    phone: str
    status: OrderStatus
    total: float
    created_at: datetime
    items: list[OrderItemRead]
    whatsapp_url: str | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
