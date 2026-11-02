import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core.exceptions import ConflictError, ValidationError
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.lichess import LichessConectarOut, LichessVincularIn
from app.schemas.usuario import CuentaLichessOut
from app.services.lichess_oauth_service import LichessOAuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lichess", tags=["lichess"])


def _volver(marca: str, motivo: str | None = None) -> RedirectResponse:
    base = settings.FRONTEND_URL.rstrip("/")
    query = f"lichess={marca}"
    if motivo:
        query += f"&motivo={motivo}"
    return RedirectResponse(url=f"{base}/cuenta?{query}", status_code=302)


@router.get("/conectar", response_model=LichessConectarOut)
def conectar(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> LichessConectarOut:
    return LichessConectarOut(url=LichessOAuthService(db).url_de_conexion(usuario))


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error or not code or not state:
        return _volver("error", "denegado")
    try:
        LichessOAuthService(db).completar(code, state)
    except ConflictError:
        return _volver("error", "ocupada")
    except ExpiredSignatureError:
        return _volver("error", "expirado")
    except (ValidationError, JWTError):
        return _volver("error", "datos")
    except Exception:
        logger.exception("Fallo al vincular Lichess")
        return _volver("error", "error")
    return _volver("ok")


@router.post("/vincular", response_model=CuentaLichessOut)
def vincular(
    body: LichessVincularIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> CuentaLichessOut:
    cuenta = LichessOAuthService(db).vincular_por_username(usuario, body.username)
    return CuentaLichessOut.model_validate(cuenta)


@router.delete("", status_code=204)
def desvincular(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> Response:
    LichessOAuthService(db).desvincular(usuario)
    return Response(status_code=204)
