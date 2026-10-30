from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core.exceptions import UnauthorizedError
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegistroRequest, TokenResponse
from app.schemas.usuario import PerfilOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )


@router.post("/registro", response_model=TokenResponse, status_code=201)
def registrar(
    data: RegistroRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    usuario = service.registrar(data)
    access, refresh = service.emitir_tokens(
        usuario,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, usuario=service.perfil(usuario))


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    usuario = service.autenticar(credentials)
    access, refresh = service.emitir_tokens(
        usuario,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, usuario=service.perfil(usuario))


@router.post(
    "/google",
    response_model=TokenResponse,
    responses={
        401: {"description": "Token de Google inválido o correo no verificado"},
        404: {"description": "Ese correo de Google no tiene cuenta. Hay que registrarse primero."},
    },
)
def login_con_google(
    data: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    usuario = service.autenticar_con_google(data.id_token)
    access, refresh = service.emitir_tokens(
        usuario,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, usuario=service.perfil(usuario))


@router.post("/refresh", response_model=TokenResponse)
def refrescar(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw is None:
        raise UnauthorizedError("No hay sesión activa")
    service = AuthService(db)
    access, usuario, nuevo = service.refrescar_access_token(raw)
    _set_refresh_cookie(response, nuevo)
    return TokenResponse(access_token=access, usuario=service.perfil(usuario))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw:
        AuthService(db).cerrar_sesion(raw)
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/v1/auth")


@router.get("/me", response_model=PerfilOut)
def yo(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)):
    return AuthService(db).perfil(usuario)
