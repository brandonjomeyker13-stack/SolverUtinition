class AppError(Exception):
    """Error de negocio. main.py lo traduce a HTTP; los services no importan FastAPI."""

    def __init__(self, message: str, codigo: str | None = None):
        self.message = message
        self.codigo = codigo
        super().__init__(message)


class NotFoundError(AppError):
    """-> HTTP 404"""


class ConflictError(AppError):
    """-> HTTP 409"""


class UnauthorizedError(AppError):
    """-> HTTP 401"""


class ForbiddenError(AppError):
    """-> HTTP 403"""


class ValidationError(AppError):
    """-> HTTP 422"""


class RateLimitedError(AppError):
    """-> HTTP 429. El endurecimiento de rate limit queda para después del MVP."""

    def __init__(self, message: str, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)
