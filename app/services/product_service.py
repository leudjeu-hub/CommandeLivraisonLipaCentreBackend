from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProductInUseError
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> Sequence[Product]:
        result = await self.session.execute(select(Product).order_by(Product.name))
        return result.scalars().all()

    async def get(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def create(self, data: ProductCreate) -> Product:
        product = Product(**data.model_dump())
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update(self, product_id: int, data: ProductUpdate) -> Product | None:
        product = await self.get(product_id)
        if product is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def delete(self, product_id: int) -> bool:
        product = await self.get(product_id)
        if product is None:
            return False
        if await self.session.scalar(select(exists().where(OrderItem.product_id == product_id))):
            raise ProductInUseError(product.name)
        await self.session.delete(product)
        await self.session.commit()
        return True
