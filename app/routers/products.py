from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.deps import ProductServiceDep, SessionDep, require_admin
from app.schemas.product import (
    CatalogueImport,
    CatalogueImportReport,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.services.catalogue_import import import_catalogue

router = APIRouter()

# Reading the catalogue is public; creating, editing and deleting products is for administrators.
ADMIN_ONLY = [Depends(require_admin)]

# The list is public and the same for everyone: browsers may reuse it for a minute, then show the
# stale copy while refetching in the background for ten more (a revisit on 3G skips ~30 KB gzipped).
# The site and /admin refetch with `cache: "no-cache"` after an edit: admins never see an old list.
CATALOGUE_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=600"


@router.get("/", response_model=list[ProductRead])
async def list_products(service: ProductServiceDep, response: Response) -> list[ProductRead]:
    response.headers["Cache-Control"] = CATALOGUE_CACHE_CONTROL
    return [ProductRead.model_validate(p) for p in await service.list()]


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, service: ProductServiceDep) -> ProductRead:
    product = await service.get(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return ProductRead.model_validate(product)


@router.post(
    "/", response_model=ProductRead, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_ONLY
)
async def create_product(data: ProductCreate, service: ProductServiceDep) -> ProductRead:
    return ProductRead.model_validate(await service.create(data))


@router.post("/import", response_model=CatalogueImportReport, dependencies=ADMIN_ONLY)
async def import_products(data: CatalogueImport, session: SessionDep) -> CatalogueImportReport:
    """Create or update products from a CSV file; nothing is written if any row is invalid."""
    report = await import_catalogue(session, data.content, apply=not data.dry_run)
    applied = not data.dry_run and not report.errors
    return CatalogueImportReport.model_validate({**vars(report), "applied": applied})


@router.put("/{product_id}", response_model=ProductRead, dependencies=ADMIN_ONLY)
async def update_product(
    product_id: int, data: ProductUpdate, service: ProductServiceDep
) -> ProductRead:
    product = await service.update(product_id, data)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_ONLY)
async def delete_product(product_id: int, service: ProductServiceDep) -> None:
    if not await service.delete(product_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
