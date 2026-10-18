class AppError(Exception):
    status_code: int = 400
    detail: str = ""

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class ProductNotFoundError(AppError):
    status_code = 404

    def __init__(self, product_id: int) -> None:
        super().__init__(f"Product {product_id} not found")


class InsufficientStockError(AppError):
    status_code = 400

    def __init__(self, product_name: str) -> None:
        super().__init__(f"Not enough stock for {product_name}")


class PriceOnRequestError(AppError):
    status_code = 400

    def __init__(self, product_name: str) -> None:
        super().__init__(f"{product_name} is priced on request and cannot be ordered directly")
