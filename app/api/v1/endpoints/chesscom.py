import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.chesscom import ChesscomConectarOut, ChesscomVincularIn
from app.schemas.usuario import CuentaChesscomOut
from app.services.chesscom_oauth_service import ChesscomOAuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chesscom", tags=["chesscom"])


def _volver(marca: str) -> RedirectResponse:
    base = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{base}/cuenta?chesscom={marca}", status_code=302)


@router.get("/conectar", response_model=ChesscomConectarOut)
def conectar(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> ChesscomConectarOut:
    return ChesscomConectarOut(url=ChesscomOAuthService(db).url_de_conexion(usuario))


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not code or not state:
        return _volver("error")
    try:
        ChesscomOAuthService(db).completar(code, state)
    except AppError as exc:
        logger.info("No se pudo vincular Chess.com: %s", exc.message)
        return _volver("error")
    except Exception:
        logger.exception("Fallo al vincular Chess.com")
        return _volver("error")
    return _volver("ok")


@router.post("/vincular", response_model=CuentaChesscomOut)
def vincular(
    body: ChesscomVincularIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> CuentaChesscomOut:
    cuenta = ChesscomOAuthService(db).vincular_por_username(usuario, body.username)
    return CuentaChesscomOut.model_validate(cuenta)


@router.delete("", status_code=204)
def desvincular(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> Response:
    ChesscomOAuthService(db).desvincular(usuario)
    return Response(status_code=204)
