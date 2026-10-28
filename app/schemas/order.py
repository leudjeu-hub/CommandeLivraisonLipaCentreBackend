from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.order import OrderKind, OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10_000)


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


class OrderSubmit(BaseModel):
    """An order or quote request sent by the site's form (no account needed).

    Prices come from the catalogue, not from the request. Stock is not taken: the shop confirms
    the order with the customer first (WhatsApp or e-mail, as before).
    """

    kind: OrderKind = OrderKind.ORDER
    customer_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    area: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=500)
    slot: str = Field(default="", max_length=120)
    payment: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=2000)
    delivery_fee: float | None = Field(default=None, ge=0, le=1_000_000)
    items: list[OrderItemCreate] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _order_has_items(self) -> "OrderSubmit":
        if self.kind == OrderKind.ORDER and not self.items:
            raise ValueError("An order needs at least one item")
        return self


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: OrderKind
    customer_name: str
    phone: str
    status: OrderStatus
    total: float
    delivery_fee: float | None
    area: str | None
    address: str | None
    slot: str | None
    payment: str | None
    notes: str | None
    created_at: datetime
    status_changed_at: datetime | None
    items: list[OrderItemRead]
    whatsapp_url: str | None = None
    # Only in the answer to a guest's POST /submit (never stored or listed): see OrderClaim
    claim_code: str | None = None

    @field_validator("created_at", "status_changed_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        """Stored times are naive UTC: say so, so browsers convert them to local time."""
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class OrderAdminRead(OrderRead):
    """What managers and administrators see: the shop's internal remarks too. Customers get
    OrderRead (POST /submit, GET /mine), which has no such field."""

    admin_notes: str | None


class AdminNotesUpdate(BaseModel):
    """Internal remarks on an order or an account; empty clears them."""

    admin_notes: str = Field(max_length=2000)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderClaim(BaseModel):
    """Codes a browser received for orders sent without an account, to attach them to the account
    the customer has since logged in to."""

    codes: list[str] = Field(min_length=1, max_length=20)


class OrderClaimResult(BaseModel):
    claimed: int
