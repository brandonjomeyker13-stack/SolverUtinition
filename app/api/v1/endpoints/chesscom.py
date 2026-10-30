from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.schemas.chesscom import ChesscomConectarOut, ChesscomEstadoOut, ChesscomVincularIn
from app.services.chesscom_oauth_service import ChesscomOAuthService

router = APIRouter(prefix="/chesscom", tags=["chesscom"])


@router.post("/vincular", response_model=ChesscomEstadoOut)
def vincular(
    data: ChesscomVincularIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    cuenta = ChesscomOAuthService(db).vincular_por_username(usuario, data.username)
    return ChesscomEstadoOut(
        vinculada=True,
        username=cuenta.username,
        username_visible=cuenta.username_visible,
    )


@router.get("/conectar", response_model=ChesscomConectarOut)
def conectar(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    url = ChesscomOAuthService(db).url_de_conexion(usuario)
    return ChesscomConectarOut(url=url)


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    destino = settings.FRONTEND_URL.rstrip("/")
    try:
        ChesscomOAuthService(db).completar(code, state)
    except (JWTError, AppError, ValueError, KeyError):
        return RedirectResponse(f"{destino}/cuenta?chesscom=error")
    return RedirectResponse(f"{destino}/cuenta?chesscom=ok")


@router.get("/estado", response_model=ChesscomEstadoOut)
def estado(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    cuenta = CuentaChesscomRepository(db).get_by_usuario_id(usuario.id)
    if cuenta is None:
        return ChesscomEstadoOut(vinculada=False)
    return ChesscomEstadoOut(
        vinculada=True,
        username=cuenta.username,
        username_visible=cuenta.username_visible,
    )


@router.delete("", status_code=204)
def desvincular(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    ChesscomOAuthService(db).desvincular(usuario)
