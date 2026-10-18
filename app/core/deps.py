from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.services.order_service import OrderService
from app.services.product_service import ProductService

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def get_product_service(session: SessionDep) -> ProductService:
    return ProductService(session)


async def get_order_service(session: SessionDep) -> OrderService:
    return OrderService(session)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
