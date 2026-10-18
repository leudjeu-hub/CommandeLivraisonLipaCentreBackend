from fastapi import APIRouter, HTTPException, status

from app.core.deps import ProductServiceDep
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter()


@router.get("/", response_model=list[ProductRead])
async def list_products(service: ProductServiceDep) -> list[ProductRead]:
    return [ProductRead.model_validate(p) for p in await service.list()]


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, service: ProductServiceDep) -> ProductRead:
    product = await service.get(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return ProductRead.model_validate(product)


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, service: ProductServiceDep) -> ProductRead:
    return ProductRead.model_validate(await service.create(data))


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int, data: ProductUpdate, service: ProductServiceDep
) -> ProductRead:
    product = await service.update(product_id, data)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, service: ProductServiceDep) -> None:
    if not await service.delete(product_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
