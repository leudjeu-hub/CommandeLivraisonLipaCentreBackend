from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductCategory

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class ProductCreate(BaseModel):
    category: ProductCategory
    price: float | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=500)
    label: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    description_en: str | None = Field(default=None, max_length=500)
    label_en: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    available: bool = True
    status: str | None = Field(default=None, max_length=50)
    image: str | None = Field(default=None, max_length=255)
    stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    category: ProductCategory | None = None
    price: float | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    label: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    description_en: str | None = Field(default=None, max_length=500)
    label_en: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    available: bool | None = None
    status: str | None = Field(default=None, max_length=50)
    image: str | None = Field(default=None, max_length=255)
    stock: int | None = Field(default=None, ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: ProductCategory
    price: float | None
    name: str
    description: str
    label: str | None
    name_en: str | None
    description_en: str | None
    label_en: str | None
    color: str | None
    available: bool
    status: str | None
    image: str | None
    stock: int
