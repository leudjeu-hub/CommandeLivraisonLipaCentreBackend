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


class ProductInUseError(AppError):
    status_code = 409

    def __init__(self, product_name: str) -> None:
        super().__init__(
            f"{product_name} appears in orders and cannot be deleted; mark it unavailable instead"
        )


class EmailAlreadyUsedError(AppError):
    status_code = 409
    detail = "An account already exists for this e-mail"


class InvalidCredentialsError(AppError):
    status_code = 401
    detail = "Invalid e-mail or password"


class UserNotFoundError(AppError):
    status_code = 404

    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")


class LastAdminError(AppError):
    status_code = 409
    detail = "The last administrator cannot be demoted, blocked or deleted"


class AccountBlockedError(AppError):
    status_code = 403
    detail = "This account is blocked"


class OwnAccountError(AppError):
    status_code = 409
    detail = "You cannot block or delete your own account"


class UserHasTimeEntriesError(AppError):
    status_code = 409
    detail = "This account has recorded hours and cannot be deleted; block it instead"


class OwnTimeEntryError(AppError):
    status_code = 403
    detail = "Only an administrator can correct your own hours"


class AlreadyClockedInError(AppError):
    status_code = 409
    detail = "Already clocked in"


class NotClockedInError(AppError):
    status_code = 409
    detail = "Not clocked in"


class TimeEntryNotFoundError(AppError):
    status_code = 404

    def __init__(self, entry_id: int) -> None:
        super().__init__(f"Time entry {entry_id} not found")
