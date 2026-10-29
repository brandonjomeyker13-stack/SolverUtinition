import hmac

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


def get_current_usuario(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if token is None:
        raise UnauthorizedError("No autenticado")

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise UnauthorizedError("Token inválido o expirado")

    usuario_id = payload.get("sub")
    if usuario_id is None:
        raise UnauthorizedError("Token inválido")

    usuario = db.get(Usuario, int(usuario_id))
    if usuario is None or not usuario.activo:
        raise UnauthorizedError("Usuario no válido")
    return usuario


def require_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    if not settings.CRON_SECRET:
        raise NotFoundError("No encontrado")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise UnauthorizedError("Cron no autorizado")
