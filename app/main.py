import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.cors import configurar_cors
from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    ValidationError,
)
from app.db.session import engine

logging.basicConfig(level=logging.INFO if settings.is_production else logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

configurar_cors(app)

_ERROR_STATUS_MAP = {
    NotFoundError: 404,
    ConflictError: 409,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    ValidationError: 422,
    RateLimitedError: 429,
}


@app.exception_handler(AppError)
def handle_app_error(_request: Request, exc: AppError):
    status_code = _ERROR_STATUS_MAP.get(type(exc), 400)
    headers = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
    cuerpo: dict[str, str] = {"detail": exc.message}
    if exc.codigo:
        cuerpo["codigo"] = exc.codigo
    return JSONResponse(status_code=status_code, content=cuerpo, headers=headers)


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    """¿Está vivo el proceso? Lo usa Render para no reiniciar en bucle."""
    return {"status": "ok"}


@app.get("/listo")
def readiness_check():
    """¿Puede atender de verdad? Esto sí toca la base."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except Exception:
        logger.error("La base de datos no responde", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "sin_base_de_datos"})
    return {"status": "ok"}
